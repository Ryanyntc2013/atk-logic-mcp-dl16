"""Application layer shared by MCP tools and local CLI."""
from __future__ import annotations

import json
import re
import hashlib
from typing import Any

from . import backend
from .analysis import (glitch_filter, measure_pwm, measure_skew, preview_edges,
                       search_conditions, to_edges_csv, to_samples_csv, to_vcd)
from .artifacts import Waveform, load_atkdl, load_capture
from .config import CAPTURE_ID_RE, CaptureRequest, captures_dir, exports_dir
from .decoders import decode_i2c, decode_spi, decode_uart


def logic_stream_start(experimental_opt_in: bool = False, safety_confirmation: str = "",
                       channels: list[int] | None = None, sample_rate_hz: int = 20_000_000,
                       duration_ms: int = 20, threshold_voltage: float = 1.6,
                       raw_rx_logging: bool = False, raw_rx_max_bytes: int = 33_554_432) -> dict:
    """EXPERIMENTAL Stream: requires CONFIRMED_SAFE_WIRING_GUI_CLOSED; all16 uncropped artifacts remain INCOMPLETE/UNKNOWN, never analysis-ready."""
    return backend.stream_start(experimental_opt_in=experimental_opt_in,
        safety_confirmation=safety_confirmation, channels=channels, sample_rate_hz=sample_rate_hz,
        duration_ms=duration_ms, threshold_voltage=threshold_voltage,
        raw_rx_logging=raw_rx_logging, raw_rx_max_bytes=raw_rx_max_bytes)


def logic_stream_poll(operation_id: str) -> dict:
    """Bounded experimental operation status; partial packed bytes are untrusted."""
    return backend.stream_control(operation_id)


def logic_stream_cancel(operation_id: str) -> dict:
    """Request cooperative same-owner stop; poll until finished, then close session."""
    return backend.stream_control(operation_id, cancel=True)


def logic_status() -> dict[str, Any]:
    return backend.status()


def logic_capture(channels: list[int] | None = None, sample_rate_hz: int = 20_000_000,
                  duration_ms: int = 20, threshold_voltage: float = 1.6,
                  trigger: str = "immediate", timeout_s: float = 45.0,
                  trigger_position_percent: float | None = None,
                  trigger_timeout_sec: int | None = None) -> dict[str, Any]:
    return backend.capture(CaptureRequest(tuple(channels if channels is not None else [0, 1]),
                                          sample_rate_hz, duration_ms, threshold_voltage, trigger),
                           timeout_s, trigger_position_percent, trigger_timeout_sec)


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
                 out_name: str | None = None, overwrite: bool = False) -> dict[str, Any]:
    """Write a compact VCD / edge CSV / full sample CSV of one channel; return the path."""
    try:
        wave = _load(capture_id, channel, atkdl_file=atkdl_file)
        if fmt == "vcd":
            content, ext = to_vcd(wave), "vcd"
        elif fmt in ("edges", "edges_csv", "csv"):
            content, ext = to_edges_csv(wave, polarity=polarity), "csv"
        elif fmt == "samples":
            content, ext = to_samples_csv(wave), "csv"
        else:
            raise ValueError("fmt must be 'vcd', 'edges' or 'samples'")
        name = out_name or f"{capture_id}_ch{channel:02d}.{ext}"
        if not _EXPORT_NAME_RE.fullmatch(name):
            raise ValueError("Unsafe export file name")
        path = exports_dir() / name
        if path.exists() and not overwrite:
            raise ValueError("Export file exists; pass overwrite=true to replace it")
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
                 atkdl_file: str | None = None, out_name: str | None = None,
                 overwrite: bool = False) -> dict[str, Any]:
    """Create a new, provenance-preserving capture; NEVER modify an existing capture.

    `overwrite` is retained for API compatibility but intentionally cannot bypass
    protection on capture directories (including previously derived captures).
    """
    try:
        wave = _load(capture_id, channel, atkdl_file=atkdl_file)
        new_id = out_name or f"{capture_id}-filt{min_pulse_samples}-ch{channel:02d}"
        if not CAPTURE_ID_RE.fullmatch(new_id) or new_id in (".", ".."):
            raise ValueError("Unsafe derived capture id")
        if not atkdl_file and new_id == capture_id:
            raise ValueError("In-place filtering is forbidden; source capture is immutable")
        folder = captures_dir() / new_id
        # Exclusive creation prevents destroying originals or mixing old/new channels.
        # No existing directory is writable through this analysis operation.
        if folder.exists() or folder.is_symlink():
            raise ValueError("Capture ID exists; use a new derived capture ID (overwrite forbidden)")
        filtered, removed = glitch_filter(wave.raw, wave.samples,
                                          min_pulse_samples=min_pulse_samples)
        original = wave.metadata
        meta = {
            "capture_id": new_id,
            "derived_from": str(wave.metadata.get("archive_path", atkdl_file)) if atkdl_file else capture_id,
            "transform": "glitch_filter", "processing_status": "COMPLETE",
            "min_pulse_samples": min_pulse_samples, "channel": channel,
            "sample_rate": wave.sample_rate_hz, "requested_samples": wave.samples,
            "sample_counts": {str(channel): wave.samples},
            "data_integrity": wave.integrity if wave.integrity == "COMPLETE" else "UNVERIFIED",
            # These describe the source acquisition, not the success of filtering.
            "capture_complete_received": bool(original.get("capture_complete_received", False)),
            "trigger_ack_received": bool(original.get("trigger_ack_received", False)),
            "evidence_source": "DERIVED", "source_evidence_source": wave.source,
            "source_integrity": wave.integrity,
            "source_sha256": hashlib.sha256(wave.raw).hexdigest(),
        }
        folder.mkdir(parents=False, exist_ok=False)
        try:
            (folder / f"ch{channel:02d}.bits").write_bytes(filtered)
            # Publish metadata LAST; an interrupted write cannot be mistaken for complete.
            (folder / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
        except BaseException:
            # Only delete the newly-created folder; never remove an existing capture.
            from shutil import rmtree
            rmtree(folder, ignore_errors=True)
            raise
        return {"success": True, "derived_capture_id": new_id, "channel": channel,
                "removed_pulses": removed, "path": str(folder),
                "source_evidence": wave.source, "source_integrity": wave.integrity,
                "source_sha256": meta["source_sha256"], "integrity": meta["data_integrity"]}
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


def logic_pwm(output: int, action: str = "configure", frequency_hz: int = 1000,
              duty_percent: float = 50.0, confirm_safe_wiring: bool = False) -> dict[str, Any]:
    return backend.pwm(output, action, frequency_hz, duty_percent, confirm_safe_wiring)


def logic_session_close() -> dict[str, Any]:
    return backend.close_session()


def logic_sigrok(vcd_file: str, decoder: str, channels: dict[str, int],
                 options: dict[str, str] | None = None, timeout_s: float = 30) -> dict[str, Any]:
    from pathlib import Path
    from .sigrok import decode_vcd
    try:
        return decode_vcd(Path(vcd_file), decoder, channels, options, timeout_s)
    except (OSError, ValueError, TypeError) as exc:
        return {"success": False, "error_code": "SIGROK_INPUT_INVALID", "message": str(exc)[:1024]}


def logic_export_atkdl(capture_id: str, channels: list[int], out_name: str) -> dict[str, Any]:
    from pathlib import Path
    from .atkdl_export import write_atkdl
    try:
        if not out_name or Path(out_name).name != out_name or out_name in (".", ".."):
            raise ValueError("out_name must be a simple .atkdl filename")
        return write_atkdl([load_capture(capture_id, ch) for ch in channels], exports_dir() / out_name)
    except (OSError, ValueError, KeyError) as exc:
        return {"success": False, "error_code": "ATKDL_EXPORT_INVALID", "message": str(exc)}


def logic_buffer_start(channels: list[int], sample_rate_hz: int = 20_000_000,
                       duration_ms: int = 20, threshold_voltage: float = 1.6,
                       trigger_timeout_sec: int = 30) -> dict[str, Any]:
    return backend.buffer_start(CaptureRequest(tuple(channels), sample_rate_hz, duration_ms,
                                               threshold_voltage), trigger_timeout_sec)


def logic_buffer_poll(operation_id: str) -> dict[str, Any]:
    return backend.buffer_control(operation_id)


def logic_buffer_cancel(operation_id: str) -> dict[str, Any]:
    return backend.buffer_control(operation_id, cancel=True)


def logic_self_test(confirm_safe_wiring: bool = False) -> dict[str, Any]:
    """Run automated hardware end-to-end self-test on loopback channels (CH8=PWM0, CH14=PWM1)."""
    from pathlib import Path
    import time
    if not confirm_safe_wiring:
        return {
            "success": False,
            "error_code": "SAFETY_CONFIRMATION_REQUIRED",
            "message": "Self-test requires confirm_safe_wiring=True confirming CH8 connected to PWM0 and CH14 connected to PWM1 with GUI closed.",
        }
    try:
        logic_session_close()
        st = logic_status()
        if not st.get("connected"):
            return {"success": False, "error_code": "DEVICE_NOT_CONNECTED", "message": "DL16 device is not connected", "status": st}

        p0 = logic_pwm(0, "configure", 1000, 50.0, confirm_safe_wiring=True)
        p1 = logic_pwm(1, "configure", 2000, 50.0, confirm_safe_wiring=True)
        if not p0.get("success") or not p1.get("success"):
            return {"success": False, "error_code": "PWM_CONFIG_FAILED", "pwm0": p0, "pwm1": p1}

        buf = logic_capture(channels=[8, 14], sample_rate_hz=20_000_000, duration_ms=20, threshold_voltage=1.6)
        if not buf.get("success"):
            return {"success": False, "error_code": "BUFFER_CAPTURE_FAILED", "buffer_capture": buf}
        buf_cid = buf.get("capture_id")
        buf_p8 = logic_measure_pwm(buf_cid, 8)
        buf_p14 = logic_measure_pwm(buf_cid, 14)

        logic_session_close()
        p0 = logic_pwm(0, "configure", 1000, 50.0, confirm_safe_wiring=True)
        p1 = logic_pwm(1, "configure", 2000, 50.0, confirm_safe_wiring=True)
        if not p0.get("success") or not p1.get("success"):
            return {"success": False, "error_code": "STREAM_PWM_CONFIG_FAILED", "pwm0": p0, "pwm1": p1}

        str_start = logic_stream_start(
            experimental_opt_in=True,
            safety_confirmation="CONFIRMED_SAFE_WIRING_GUI_CLOSED",
            channels=[8, 14],
            sample_rate_hz=1_000_000,
            duration_ms=100,
            threshold_voltage=1.6,
        )
        op_id = str_start.get("operation_id")
        if not op_id:
            return {"success": False, "error_code": "STREAM_START_FAILED", "stream_start": str_start}

        t0 = time.monotonic()
        while True:
            poll = logic_stream_poll(op_id)
            if poll.get("state") == "finished":
                break
            time.sleep(0.02)
            if time.monotonic() - t0 > 10:
                return {"success": False, "error_code": "STREAM_TIMEOUT", "poll": poll}

        str_res = poll.get("response", {}).get("result", {})
        str_dir = str_res.get("artifact_directory", "")
        str_cid = Path(str_dir).name
        str_p8 = logic_measure_pwm(str_cid, 8)
        str_p14 = logic_measure_pwm(str_cid, 14)

        logic_session_close()

        buf_ok = (990 <= buf_p8.get("frequency_hz_median", 0) <= 1010 and
                  1980 <= buf_p14.get("frequency_hz_median", 0) <= 2020)
        str_ok = (990 <= str_p8.get("frequency_hz_median", 0) <= 1010 and
                  1980 <= str_p14.get("frequency_hz_median", 0) <= 2020)

        all_ok = buf_ok and str_ok
        return {
            "success": all_ok,
            "overall_health": "HEALTHY" if all_ok else "DEGRADED",
            "device": st.get("details", {}).get("model", "DL16"),
            "buffer_capture": {
                "ok": buf_ok,
                "capture_id": buf_cid,
                "ch8_freq_hz": buf_p8.get("frequency_hz_median"),
                "ch14_freq_hz": buf_p14.get("frequency_hz_median"),
                "ch8_jitter_rms_ns": buf_p8.get("period_ns_jitter_rms"),
                "ch14_jitter_rms_ns": buf_p14.get("period_ns_jitter_rms"),
            },
            "stream_capture": {
                "ok": str_ok,
                "capture_id": str_cid,
                "stored_bytes": str_res.get("stored_bytes"),
                "reads": str_res.get("reads"),
                "ch8_freq_hz": str_p8.get("frequency_hz_median"),
                "ch14_freq_hz": str_p14.get("frequency_hz_median"),
            },
        }
    except Exception as exc:
        logic_session_close()
        return {"success": False, "error_code": "SELF_TEST_EXCEPTION", "message": str(exc)}

