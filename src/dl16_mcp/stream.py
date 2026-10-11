"""Offline-only stream prototype for DL16 logic analyzer (DL16-TASK-036).

NOTE: Native live stream / cancellation handlers are NOT implemented on hardware/C++.
This module provides strictly offline synthetic capture recording, incremental disk
append, byte budgeting, and safe cancellation semantics for future protocol integration.
All data sources are explicitly labelled SYNTHETIC_OFFLINE or CONTRACT_MOCK.
"""

from __future__ import annotations

import contextlib
import json
import math
import shutil
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

MAX_STREAM_SAMPLE_RATE_HZ = 20_000_000
MAX_STREAM_CHANNELS = 2
MAX_STREAM_DURATION_SECONDS = 30.0
MAX_STREAM_BYTE_BUDGET = 200 * 1024 * 1024  # 200 MB hard safety cap


class StreamError(RuntimeError):
    def __init__(self, code: str, message: str, *, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


@dataclass
class StreamConfig:
    channels: list[int]
    sample_rate_hz: int
    duration_s: float
    output_dir: Path
    capture_id: str
    threshold_voltage: float = 1.6
    trigger: str = "immediate"
    enable_rle: bool = False
    evidence_source: str = "SYNTHETIC_OFFLINE"

    def validate(self) -> None:
        if self.evidence_source not in ("SYNTHETIC_OFFLINE", "CONTRACT_MOCK", "UNKNOWN"):
            raise StreamError(
                "INVALID_EVIDENCE_SOURCE",
                "evidence_source must be SYNTHETIC_OFFLINE, CONTRACT_MOCK, or UNKNOWN; hardware stream is unimplemented",
            )
        if self.enable_rle:
            raise StreamError("UNSUPPORTED_MODE", "RLE compression is not supported in streaming mode")
        if not isinstance(self.channels, (list, tuple)) or not self.channels:
            raise StreamError("INVALID_STREAM_CONFIG", "channels must be a non-empty list or tuple")
        if len(self.channels) > MAX_STREAM_CHANNELS:
            raise StreamError(
                "INVALID_STREAM_CONFIG",
                f"streaming channels cap is {MAX_STREAM_CHANNELS}, requested {len(self.channels)}",
            )
        for ch in self.channels:
            if not isinstance(ch, int) or isinstance(ch, bool) or ch < 0 or ch > 15:
                raise StreamError("INVALID_STREAM_CONFIG", f"channel {ch} must be an integer in [0, 15]")
        if len(set(self.channels)) != len(self.channels):
            raise StreamError("INVALID_STREAM_CONFIG", "duplicate channels not allowed")

        if (
            not isinstance(self.sample_rate_hz, int)
            or isinstance(self.sample_rate_hz, bool)
            or self.sample_rate_hz <= 0
            or self.sample_rate_hz > MAX_STREAM_SAMPLE_RATE_HZ
        ):
            raise StreamError(
                "INVALID_STREAM_CONFIG",
                f"sample_rate_hz must be a positive integer in [1, {MAX_STREAM_SAMPLE_RATE_HZ}]",
            )

        if (
            not isinstance(self.duration_s, (int, float))
            or isinstance(self.duration_s, bool)
            or not math.isfinite(self.duration_s)
            or self.duration_s <= 0
            or self.duration_s > MAX_STREAM_DURATION_SECONDS
        ):
            raise StreamError(
                "INVALID_STREAM_CONFIG",
                f"duration_s must be a finite number in (0, {MAX_STREAM_DURATION_SECONDS}]",
            )

        if (
            not isinstance(self.threshold_voltage, (int, float))
            or isinstance(self.threshold_voltage, bool)
            or not math.isfinite(self.threshold_voltage)
            or self.threshold_voltage < -5.0
            or self.threshold_voltage > 5.0
        ):
            raise StreamError(
                "INVALID_STREAM_CONFIG", "threshold_voltage must be a finite number in [-5.0, 5.0]"
            )

        if not isinstance(self.capture_id, str) or not self.capture_id.strip():
            raise StreamError("INVALID_STREAM_CONFIG", "capture_id must be a non-empty string")
        cid = self.capture_id.strip()
        if cid in (".", "..") or "/" in cid or "\\" in cid or any(c in cid for c in r':*?"<>|'):
            raise StreamError(
                "INVALID_STREAM_CONFIG", f"capture_id '{cid}' is unsafe or contains invalid characters"
            )

    @property
    def expected_samples_per_channel(self) -> int:
        return math.ceil(self.sample_rate_hz * self.duration_s)

    @property
    def expected_bytes_per_channel(self) -> int:
        return (self.expected_samples_per_channel + 7) // 8


@dataclass
class StreamProvenance:
    capture_id: str
    channels: list[int]
    sample_rate_hz: int
    duration_s: float
    evidence_source: str
    status: str  # "in_progress", "completed", "cancelled", "error"
    total_samples: dict[int, int] = field(default_factory=dict)
    total_bytes: dict[int, int] = field(default_factory=dict)
    chunks_written: int = 0
    start_time: float = 0.0
    end_time: float = 0.0
    cancelled_by_user: bool = False
    error_code: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "capture_id": self.capture_id,
            "channels": self.channels,
            "sample_rate_hz": self.sample_rate_hz,
            "duration_s": self.duration_s,
            "evidence_source": self.evidence_source,
            "status": self.status,
            "total_samples": {str(k): v for k, v in self.total_samples.items()},
            "total_bytes": {str(k): v for k, v in self.total_bytes.items()},
            "chunks_written": self.chunks_written,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "cancelled_by_user": self.cancelled_by_user,
            "error_code": self.error_code,
            "error_message": self.error_message,
        }


class CancellationToken:
    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()


class StreamWriter:
    def __init__(self, config: StreamConfig) -> None:
        # Mandatory validation BEFORE any file or directory operation
        config.validate()
        self.config = config
        self.output_dir = Path(config.output_dir)
        self.stream_dir = self.output_dir / config.capture_id
        self._files: dict[int, Any] = {}
        self._stack = contextlib.ExitStack()
        self.provenance = StreamProvenance(
            capture_id=config.capture_id,
            channels=list(config.channels),
            sample_rate_hz=config.sample_rate_hz,
            duration_s=config.duration_s,
            evidence_source=config.evidence_source,
            status="in_progress",
            total_samples={ch: 0 for ch in config.channels},
            total_bytes={ch: 0 for ch in config.channels},
            start_time=time.time(),
        )
        self._init_files()

    def _init_files(self) -> None:
        # Create directory with exist_ok=False to prevent overwrite
        try:
            self.stream_dir.mkdir(parents=True, exist_ok=False)
        except FileExistsError as exc:
            raise StreamError(
                "DESTINATION_EXISTS",
                f"stream directory {self.stream_dir} already exists, overwrite forbidden",
            ) from exc

        opened_files = []
        try:
            for ch in self.config.channels:
                channel_file = self.stream_dir / f"ch{ch:02d}.stream.bin"
                # Open with 'xb' (exclusive creation)
                f = self._stack.enter_context(channel_file.open("xb"))
                opened_files.append(f)
                self._files[ch] = f
            self._save_meta()
        except OSError as exc:
            try:
                self._stack.close()
            finally:
                shutil.rmtree(self.stream_dir, ignore_errors=True)
            raise StreamError("STREAM_INIT_FAILED", f"failed to initialize stream files: {exc}") from exc

    def write_chunk(self, channel_chunks: dict[int, bytes]) -> None:
        if self.provenance.status not in ("in_progress",):
            raise StreamError("STREAM_CLOSED", f"stream already {self.provenance.status}")

        total_so_far = sum(self.provenance.total_bytes.values())
        incoming_bytes = sum(len(b) for b in channel_chunks.values())
        if total_so_far + incoming_bytes > MAX_STREAM_BYTE_BUDGET:
            self.provenance.status = "error"
            self.provenance.error_code = "BYTE_BUDGET_EXCEEDED"
            self.provenance.error_message = (
                f"exceeded maximum streaming budget {MAX_STREAM_BYTE_BUDGET} bytes"
            )
            self.close()
            raise StreamError("BYTE_BUDGET_EXCEEDED", self.provenance.error_message)

        for ch, data in channel_chunks.items():
            if ch not in self._files:
                continue
            if data:
                self._files[ch].write(data)
                self._files[ch].flush()
                self.provenance.total_bytes[ch] += len(data)
                self.provenance.total_samples[ch] += len(data) * 8

        self.provenance.chunks_written += 1
        self._save_meta()

    def _save_meta(self) -> None:
        meta_file = self.stream_dir / "stream_meta.json"
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(self.provenance.to_dict(), f, indent=2)

    def mark_completed_if_verified(self) -> None:
        expected_samples = self.config.expected_samples_per_channel
        for ch in self.config.channels:
            actual = self.provenance.total_samples.get(ch, 0)
            if actual < expected_samples:
                raise StreamError(
                    "INCOMPLETE_STREAM", f"channel {ch} sample deficit ({actual} < {expected_samples})"
                )

        self.provenance.status = "completed"
        self.provenance.end_time = time.time()
        self.close()

    def mark_cancelled(self) -> None:
        self.provenance.status = "cancelled"
        self.provenance.cancelled_by_user = True
        self.provenance.end_time = time.time()
        self.close()

    def mark_error(self, code: str, msg: str) -> None:
        self.provenance.status = "error"
        self.provenance.error_code = code
        self.provenance.error_message = msg
        self.provenance.end_time = time.time()
        self.close()

    def close(self) -> None:
        self._stack.close()
        self._save_meta()


class StreamSessionRunner:
    def __init__(
        self, session_client: Any, writer: StreamWriter, cancel_token: CancellationToken | None = None
    ):
        self.session_client = session_client
        self.writer = writer
        self.cancel_token = cancel_token or CancellationToken()

    def run_bounded(
        self,
        poll_interval_s: float = 0.05,
        chunk_source_fn: Callable[[], dict[int, bytes] | None] | None = None,
    ) -> StreamProvenance:
        config = self.writer.config
        start = time.time()
        max_duration = config.duration_s

        try:
            while True:
                if self.cancel_token.is_cancelled:
                    self.writer.mark_cancelled()
                    break

                elapsed = time.time() - start
                if elapsed >= max_duration:
                    self.writer.mark_completed_if_verified()
                    break

                if chunk_source_fn is not None:
                    chunks = chunk_source_fn()
                    if chunks is None:
                        self.writer.mark_completed_if_verified()
                        break
                    if chunks:
                        self.writer.write_chunk(chunks)

                time.sleep(poll_interval_s)

        except Exception as exc:
            if self.writer.provenance.status == "in_progress":
                self.writer.mark_error("STREAM_RUNNER_ERROR", str(exc))
            raise
        return self.writer.provenance
