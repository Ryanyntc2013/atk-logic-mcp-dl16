"""Strict offline loading of captured channels and vendor .atkdl archives.

A file's self-declared evidence_source is NOT a cryptographic hardware attestation.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
import zipfile
from typing import Any

from .config import CAPTURE_ID_RE, captures_dir


@dataclass(frozen=True)
class Waveform:
    channel: int
    raw: bytes
    samples: int
    sample_rate_hz: float
    integrity: str
    source: str
    metadata: dict[str, Any]


def _sample_rate(metadata: dict) -> float:
    val = metadata.get("sample_rate", metadata.get("sample_rate_hz"))
    try:
        val = float(val)
    except (ValueError, TypeError) as exc:
        raise ValueError("Missing or invalid sample_rate metadata") from exc
    if not (0 < val <= 1_000_000_000):
        raise ValueError("Invalid sample rate")
    return val


def _validate_channel(channel: int) -> None:
    if not isinstance(channel, int) or not 0 <= channel <= 15:
        raise ValueError("channel must be integer 0..15")


def load_capture(capture_id: str, channel: int) -> Waveform:
    """Load a native CLI capture from DL16_DATA_DIR/captures/<capture_id>."""
    _validate_channel(channel)
    if not CAPTURE_ID_RE.fullmatch(capture_id) or capture_id in (".", ".."):
        raise ValueError("Unsafe capture_id")
    root = captures_dir().resolve()
    folder = (root / capture_id).resolve()
    if root not in folder.parents:
        raise ValueError("Capture outside artifact root")
    with (folder / "meta.json").open("r", encoding="utf-8") as file:
        meta = json.load(file)
    if meta.get("partial_uncropped") is True:
        raise ValueError("Partial uncropped BUFFER artifacts are not analysis-ready")
    raw = (folder / f"ch{channel:02d}.bits").read_bytes()
    sr = _sample_rate(meta)
    channel_counts = meta.get("sample_counts", {})
    samples = int(channel_counts.get(str(channel), len(raw) * 8))
    requested = int(meta.get("requested_samples", samples))
    complete = (len(raw) * 8 >= requested and samples >= requested and
                str(meta.get("data_integrity", "UNKNOWN")).upper() == "COMPLETE" and
                bool(meta.get("capture_complete_received", False)) and
                bool(meta.get("trigger_ack_received", False)))
    integrity = "COMPLETE" if complete else "UNVERIFIED"
    if samples < 1 or len(raw) * 8 < samples:
        raise ValueError("Capture samples inconsistent with byte length")
    return Waveform(channel, raw, min(samples, requested), sr, integrity,
                    str(meta.get("evidence_source", "UNKNOWN")), meta)


def load_atkdl(path: str | Path, channel: int) -> Waveform:
    """Read an official archive for offline analysis; never mark it REAL_HARDWARE.

    Does not assume that byte count alone proves the capture was hardware valid.
    """
    _validate_channel(channel)
    archive_path = Path(path).expanduser().resolve()
    if archive_path.suffix.lower() != ".atkdl":
        raise ValueError("Expected .atkdl archive")
    with zipfile.ZipFile(archive_path) as z:
        # Official archives may split large channels into N sequential pieces.
        pieces = []
        pattern = re.compile(rf"{channel}/{channel}-(\d+)\.bin")
        for info in z.infolist():
            found = pattern.fullmatch(info.filename)
            if found:
                pieces.append((int(found.group(1)), info))
        pieces.sort(key=lambda pair: pair[0])
        if not pieces or [n for n, _ in pieces] != list(range(len(pieces))):
            raise FileNotFoundError(f"Channel {channel} missing or segmented chunks not contiguous")
        if sum(info.file_size for _, info in pieces) > 256 * 1024 * 1024:
            raise ValueError("Archive channel exceeds 256MiB offline safety cap")
        raw = b"".join(z.read(info) for _, info in pieces)
        if "set.ini" not in z.namelist() or z.getinfo("set.ini").file_size > 1024 * 1024:
            raise ValueError("Missing/oversized set.ini")
        ini = z.read("set.ini").decode("utf-8-sig", errors="replace")
    setting = None
    for line in ini.splitlines():
        if line.strip().startswith("settingData="):
            setting = json.loads(line.partition("=")[2])
            break
    if not isinstance(setting, dict):
        raise ValueError("Missing settingData JSON in set.ini")
    sr = _sample_rate({"sample_rate": setting.get("setHz")})
    duration_ms = setting.get("setTime")
    if duration_ms is None:
        samples = len(raw) * 8
        quality = "UNVERIFIED"
    else:
        samples = int(sr * float(duration_ms) / 1000)
        quality = "OFFLINE_LENGTH_MATCH" if 0 < samples <= len(raw) * 8 else "UNVERIFIED"
    return Waveform(channel, raw, samples, sr, quality, "SAVED_ATKDL",
                    {"archive_path": str(archive_path), "setTime": duration_ms, "setHz": sr})
