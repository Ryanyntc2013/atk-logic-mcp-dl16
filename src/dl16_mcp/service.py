"""Application layer shared by MCP tools and local CLI."""
from __future__ import annotations

import json
import re
from typing import Any

from . import backend
from .analysis import (glitch_filter, measure_pwm, measure_skew, preview_edges,
                       search_conditions, to_edges_csv, to_vcd)
from .artifacts import Waveform, load_atkdl, load_capture
from .config import CAPTURE_ID_RE, CaptureRequest, captures_dir, exports_dir
from .decoders import decode_i2c, decode_spi, decode_uart


def logic_status() -> dict[str, Any]:
    return backend.status()


def logic_capture(channels: list[int] | None = None, sample_rate_hz: int = 20_000_000,
                  duration_ms: int = 20, threshold_voltage: float = 1.6,
                  trigger: str = "immediate", timeout_s: float = 45.0) -> dict[str, Any]:
    return backend.capture(CaptureRequest(tuple(channels if channels is not None else [0, 1]),
                                          sample_rate_hz, duration_ms, threshold_voltage, trigger), timeout_s)


def _load(capture_id: str, channel: int, *, atkdl_file: str | None = None) -> Waveform:
    return load_atkdl(atkdl_file, channel) if atkdl_file else load_capture(capture_id, channel)


def logic_inspect(capture_id: str, channel: int, max_edges: int = 50,
                  polarity: str = "rising", atkdl_file: str | None = None) -> dict[str, Any]:
    try:
        if polarity not in ("rising", "falling"):
            raise ValueError("polarity must be rising or falling")
        return preview_edges(_load(capture_id, channel, atkdl_file=atkdl_file),
                             polarity=polarity, limit=max_edges)
    except (ValueError, FileNotFoundError, OSError, KeyError) as exc:
        return {"success": False, "error_code": "ANALYSIS_INVALID", "message": str(exc)}


def logic_measure_skew(capture_id: str, reference_channel: int, target_channel: int,
                       polarity: str = "rising", expected_delay_ns: float = 0.0,
                       match_window_ns: float | None = None,
                       max_abs_error_ns: float | None = None,
                       atkdl_file: str | None = None) -> dict[str, Any]:
    try:
        ref = _load(capture_id, reference_channel, atkdl_file=atkdl_file)
        tar = _load(capture_id, target_channel, atkdl_file=atkdl_file)
        return measure_skew(ref, tar, polarity=polarity, expected_delay_ns=expected_delay_ns,
                            match_window_ns=match_window_ns, max_abs_error_ns=max_abs_error_ns)
    except (ValueError, FileNotFoundError, OSError, KeyError) as exc:
        return {"success": False, "error_code": "ANALYSIS_INVALID", "message": str(exc), "verdict": "NOT_EVALUATED"}


def logic_measure_pwm(capture_id: str, channel: int, atkdl_file: str | None = None) -> dict[str, Any]:
    try:
        return measure_pwm(_load(capture_id, channel, atkdl_file=atkdl_file))
    except (ValueError, FileNotFoundError, OSError, KeyError) as exc:
        return {"success": False, "error_code": "ANALYSIS_INVALID", "message": str(exc)}


_EXPORT_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


def logic_export(capture_id: str, channel: int, fmt: str = "vcd",
                 polarity: str = "rising", atkdl_file: str | None = None,
                 out_name: str | None = None) -> dict[str, Any]:
    """Write a compact VCD or edge CSV of one channel; return the path, not the bytes."""
    try:
        wave = _load(capture_id, channel, atkdl_file=atkdl_file)
        if fmt == "vcd":
            content, ext = to_vcd(wave), "vcd"
        elif fmt in ("edges", "edges_csv", "csv"):
            content, ext = to_edges_csv(wave, polarity=polarity), "csv"
        else:
            raise ValueError("fmt must be 'vcd' or 'edges'")
        name = out_name or f"{capture_id}_ch{channel:02d}.{ext}"
        if not _EXPORT_NAME_RE.fullmatch(name):
            raise ValueError("Unsafe export file name")
        path = exports_dir() / name
        path.write_text(content, encoding="utf-8")
        return {"success": True, "format": fmt, "channel": channel,
                "path": str(path), "bytes": path.stat().st_size,
                "evidence_source": wave.source, "integrity": wave.integrity}
    except (ValueError, FileNotFoundError, OSError, KeyError) as exc:
        return {"success": False, "error_code": "EXPORT_FAILED", "message": str(exc)}


_CONDITION_RE = re.compile(r"^(?:ch)?(\d{1,2})\s*[:=]\s*(rising|falling|high|low)$", re.IGNORECASE)


def _parse_condition(condition) -> tuple[int, str]:
    if isinstance(condition, (list, tuple)) and len(condition) == 2:
        channel, kind = int(condition[0]), str(condition[1]).lower()
    elif isinstance(condition, str):
        match = _CONDITION_RE.fullmatch(condition.strip())
        if not match:
            raise ValueError(f"Invalid condition: {condition!r}")
        channel, kind = int(match.group(1)), match.group(2).lower()
    else:
        raise ValueError(f"Invalid condition: {condition!r}")
    if not 0 <= channel <= 15:
        raise ValueError("Condition channel must be 0..15")
    return channel, kind


def logic_filter(capture_id: str, channel: int, min_pulse_samples: int,
                 atkdl_file: str | None = None, out_name: str | None = None) -> dict[str, Any]:
    """Write a derived capture with pulses shorter than min_pulse_samples removed."""
    try:
        wave = _load(capture_id, channel, atkdl_file=atkdl_file)
        filtered, removed = glitch_filter(wave.raw, wave.samples, min_pulse_samples=min_pulse_samples)
        new_id = out_name or f"{capture_id}-filt{min_pulse_samples}-ch{channel:02d}"
        if not CAPTURE_ID_RE.fullmatch(new_id):
            raise ValueError("Unsafe derived capture id")
        folder = captures_dir() / new_id
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"ch{channel:02d}.bits").write_bytes(filtered)
        meta = {
            "capture_id": new_id, "derived_from": capture_id, "transform": "glitch_filter",
            "min_pulse_samples": min_pulse_samples, "channel": channel,
            "sample_rate": wave.sample_rate_hz, "requested_samples": wave.samples,
            "sample_counts": {str(channel): wave.samples}, "data_integrity": "COMPLETE",
            "capture_complete_received": True, "trigger_ack_received": True,
            "evidence_source": "DERIVED",
        }
        (folder / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
        return {"success": True, "derived_capture_id": new_id, "channel": channel,
                "removed_pulses": removed, "path": str(folder), "source_evidence": wave.source}
    except (ValueError, FileNotFoundError, OSError, KeyError) as exc:
        return {"success": False, "error_code": "FILTER_FAILED", "message": str(exc)}


def logic_search(capture_id: str, conditions: list, limit: int = 100,
                 atkdl_file: str | None = None) -> dict[str, Any]:
    """Find samples matching all channel conditions (rising/falling/high/low)."""
    try:
        parsed = [_parse_condition(c) for c in conditions]
        waves: dict[int, Waveform] = {}
        for channel, _ in parsed:
            waves[channel] = _load(capture_id, channel, atkdl_file=atkdl_file)
        result = search_conditions(waves, parsed, limit=limit)
        result["evidence_source"] = next(iter(waves.values())).source
        return result
    except (ValueError, FileNotFoundError, OSError, KeyError) as exc:
        return {"success": False, "error_code": "SEARCH_FAILED", "message": str(exc)}


def logic_decode(capture_id: str, protocol: str, channels: list[int],
                 baud_rate: int = 115200, cpol: int = 0, cpha: int = 0,
                 atkdl_file: str | None = None, data_bits: int = 8, parity: str = "none",
                 stop_bits: int = 1, invert: bool = False, bit_order: str = "msb",
                 bits_per_word: int = 8) -> dict[str, Any]:
    """Decode UART/I2C/SPI with the in-repo offline decoders (no native checkout)."""
    try:
        waves = [_load(capture_id, c, atkdl_file=atkdl_file) for c in channels]
        if not waves or len({w.sample_rate_hz for w in waves}) != 1:
            raise ValueError("Decoder channels must share a sample rate")
        if protocol == "uart" and len(waves) == 1:
            data = decode_uart(waves[0], baud_rate=baud_rate, data_bits=data_bits,
                               parity=parity, stop_bits=stop_bits, invert=invert)
        elif protocol == "i2c" and len(waves) == 2:
            data = decode_i2c(waves[0], waves[1])
        elif protocol == "spi" and 2 <= len(waves) <= 4:
            data = decode_spi(waves[0], waves[1],
                              waves[2] if len(waves) >= 3 else None,
                              waves[3] if len(waves) == 4 else None,
                              cpol=cpol, cpha=cpha, bit_order=bit_order,
                              bits_per_word=bits_per_word)
        else:
            raise ValueError("Use uart:[rx], i2c:[scl,sda], spi:[clk,mosi,(miso),(cs)]")
        return {"success": True, "protocol": protocol, "channel_mapping": channels,
                "event_count": len(data), "events": data[:200],
                "truncated": len(data) > 200, "evidence_source": waves[0].source,
                "data_integrity": waves[0].integrity}
    except (ValueError, FileNotFoundError, OSError, KeyError) as exc:
        return {"success": False, "error_code": "DECODE_FAILED", "message": str(exc)}
