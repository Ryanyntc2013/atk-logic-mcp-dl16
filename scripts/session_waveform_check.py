"""Offline known-source acceptance, independent of native success flags."""
from pathlib import Path

import numpy as np


def check_pwm_bits(path: Path, samples: int, sample_rate_hz: int,
                   expected_hz: float, expected_duty: float = 0.5) -> dict:
    raw = path.read_bytes()
    if len(raw) * 8 < samples:
        return {"valid": False, "reason": "stored bits shorter than requested samples"}
    bits = np.unpackbits(np.frombuffer(raw, dtype=np.uint8), bitorder="little")[:samples]
    rises = np.flatnonzero((bits[1:] == 1) & (bits[:-1] == 0)) + 1
    periods = np.diff(rises)
    frequency = sample_rate_hz / float(np.median(periods)) if len(periods) else None
    duty = float(bits.mean())
    valid = (frequency is not None and abs(frequency - expected_hz) <= expected_hz * 0.01
             and abs(duty - expected_duty) <= 0.03)
    return {"valid": valid, "frequency_hz": frequency, "high_fraction": duty,
            "rising_edges": int(len(rises)), "samples": int(len(bits)),
            "criterion": "1% frequency / 3 percentage-point duty; uncalibrated"}
