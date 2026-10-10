"""Application layer shared by MCP tools and local CLI."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from . import backend
from .analysis import measure_pwm, measure_skew, preview_edges, to_edges_csv, to_vcd
from .artifacts import Waveform, load_atkdl, load_capture
from .config import CaptureRequest, exports_dir


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


def logic_decode(capture_id: str, protocol: str, channels: list[int],
                 baud_rate: int = 115200, cpol: int = 0, cpha: int = 0,
                 atkdl_file: str | None = None) -> dict[str, Any]:
    """Use upstream's Python decoder module after bootstrap-native (no GUI needed)."""
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    upstream = root / "external" / "ATK-Logic-Mcp"
    if not upstream.is_dir():
        return {"success": False, "error_code": "DECODER_BACKEND_MISSING",
                "message": "Run scripts/bootstrap-native.ps1 to install upstream UART/I2C/SPI decoders"}
    if str(upstream) not in sys.path:
        sys.path.insert(0, str(upstream))
    try:
        import importlib
        decoder_module = importlib.import_module("analysis.decoders")
        if not Path(decoder_module.__file__).resolve().is_relative_to(upstream.resolve()):
            raise ImportError("Refusing non-pinned analysis.decoders module")
        decode_uart, decode_i2c, decode_spi = (
            decoder_module.decode_uart, decoder_module.decode_i2c, decoder_module.decode_spi)
        waves = [_load(capture_id, c, atkdl_file=atkdl_file) for c in channels]
        if not waves or len({w.sample_rate_hz for w in waves}) != 1:
            raise ValueError("Decoder channels must share a sample rate")
        sr = waves[0].sample_rate_hz
        if protocol == "uart" and len(waves) == 1:
            data = decode_uart(waves[0].raw, sr, baud_rate=baud_rate)
        elif protocol == "i2c" and len(waves) == 2:
            data = decode_i2c(waves[0].raw, waves[1].raw, sr)
        elif protocol == "spi" and 2 <= len(waves) <= 4:
            data = decode_spi(waves[0].raw, waves[1].raw,
                              waves[2].raw if len(waves) >= 3 else None,
                              waves[3].raw if len(waves) == 4 else None,
                              sr, cpol=cpol, cpha=cpha)
        else:
            raise ValueError("Use uart:[rx], i2c:[scl,sda], spi:[clk,mosi,(miso),(cs)]")
        return {"success": True, "protocol": protocol, "channel_mapping": channels,
                "event_count": len(data), "events": data[:200],
                "truncated": len(data) > 200, "evidence_source": waves[0].source,
                "data_integrity": waves[0].integrity}
    except (ImportError, ValueError, FileNotFoundError, OSError, KeyError) as exc:
        return {"success": False, "error_code": "DECODE_FAILED", "message": str(exc)}
