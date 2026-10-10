"""Centralized workspace paths and capture input validation."""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re

SUPPORTED_RATES_HZ = frozenset(
    [1, 2, 4, 5, 10, 20, 25, 40, 50, 100, 200, 250, 500, 1000]
)
CAPTURE_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}$")


def workspace_dir() -> Path:
    path = Path(os.environ.get("DL16_DATA_DIR", "./artifacts")).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def captures_dir() -> Path:
    path = workspace_dir() / "captures"
    path.mkdir(parents=True, exist_ok=True)
    return path


@dataclass(frozen=True)
class CaptureRequest:
    channels: tuple[int, ...] = (0, 1)
    sample_rate_hz: int = 20_000_000
    duration_ms: int = 20
    threshold_voltage: float = 1.6
    trigger: str = "immediate"
    mode: str = "buffer"

    def validate(self) -> None:
        if not self.channels or len(self.channels) > 16:
            raise ValueError("Expected 1 to 16 channels")
        if len(set(self.channels)) != len(self.channels) or any(not isinstance(x, int) or x < 0 or x > 15 for x in self.channels):
            raise ValueError("Channels must be distinct integers from 0 to 15")
        if self.sample_rate_hz not in {int(mhz * 1_000_000) for mhz in SUPPORTED_RATES_HZ}:
            raise ValueError("Unsupported sample-rate preset")
        if not isinstance(self.duration_ms, int) or self.duration_ms <= 0:
            raise ValueError("Capture duration must be positive integral milliseconds")
        if not -5.0 <= self.threshold_voltage <= 5.0:
            raise ValueError("Threshold outside [-5, 5] volts")
        if self.mode != "buffer":
            raise ValueError("Only buffer mode is enabled for trusted captures; stream is not HIL-validated")
        if self.trigger != "immediate":
            match = re.fullmatch(r"ch(1[0-5]|[0-9]):(rising|falling|high|low|both|double)", self.trigger)
            if not match or int(match.group(1)) not in self.channels:
                raise ValueError("Trigger must be 'immediate' or chN:rising/falling/high/low/both for an enabled channel")
        # Conservative generic device-agnostic bound; model-specific limits remain native backend's job.
        if self.sample_rate_hz * self.duration_ms // 1000 > 1_000_000_000:
            raise ValueError("Requested capture exceeds scaffold safety cap (1G samples/channel)")
