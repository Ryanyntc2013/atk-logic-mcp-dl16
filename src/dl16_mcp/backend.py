"""Adapter to the audited native CLI maintained by gjjisadog/ATK-Logic-Mcp.

The upstream native core speaks USB/WinUSB. We DO NOT reimplement its USB protocol
here. A pinned source build is performed by scripts/bootstrap-native.ps1.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import threading
from typing import Any

from .config import CaptureRequest, captures_dir
from .session import NativeSession, SessionFailure, register_for_shutdown

# Total attempts (first try + retries) for the retryable post-capture open failure.
MAX_ATTEMPTS = 3
# Injectable sleep so offline tests do not wait on real backoff.
_sleep = time.sleep


class BackendError(RuntimeError):
    pass


def find_native_cli() -> Path | None:
    env = os.environ.get("DL16_CLI_PATH")
    if env:
        p = Path(env).expanduser()
        return p.resolve() if p.is_file() else None
    root = Path(__file__).resolve().parents[2]
    candidates = [
        root / "external/ATK-Logic-Mcp/build/Release/atk-dl16.exe",
        root / "external/ATK-Logic-Mcp/build/atk-dl16.exe",
        root / "external/ATK-Logic-Mcp/build/atk-dl16",
    ]
    for p in candidates:
        if p.is_file():
            return p
    cmd = shutil.which("atk-dl16") or shutil.which("atk-dl16.exe")
    return Path(cmd) if cmd else None


# The pinned native backend intermittently fails to parse the FPGA device-info
# packet (short/non-2048B reply); on this firmware it fails deterministically the
# first open after a completed capture (DL16-TASK-002 B6) and succeeds on retry.
_RETRYABLE_OPEN_FRAGMENT = "failed to parse fpga device info"
_SESSION_LOCK = threading.Lock()
_SESSION: NativeSession | None = None
_SESSION_PATH: Path | None = None


def _session_enabled() -> bool:
    return os.environ.get("DL16_BACKEND_MODE", "oneshot").strip().lower() == "session"


def has_owned_session() -> bool:
    """Conservative guard: self-test must not preempt an existing MCP owner."""
    with _SESSION_LOCK:
        return _SESSION is not None and not getattr(_SESSION, "_closed", False)


def _get_session(cli: Path) -> NativeSession:
    global _SESSION, _SESSION_PATH
    with _SESSION_LOCK:
        if (_SESSION is not None and _SESSION_PATH == cli
                and not _SESSION.failed):
            return _SESSION
        if _SESSION is not None:
            _SESSION.close()
        _SESSION = NativeSession(cli)
        _SESSION_PATH = cli
        register_for_shutdown(_SESSION)
        return _SESSION


def _session_status(cli: Path) -> dict[str, Any]:
    try:
        response = _get_session(cli).request({"command": "status"}, timeout_s=10.0)
        device = response.get("device", {})
        return {"connected": True, "ready": response.get("session") == "ready",
                "backend": "native-session", "cli_path": str(cli),
                "transport_open": response.get("transport_open") is True,
                "details": {"model": device.get("model"),
                            "hardware_level": device.get("hardware_level"),
                            "usb_link_speed": device.get("usb_speed"),
                            "mcu_firmware": device.get("mcu_firmware"),
                            "fpga_firmware": device.get("fpga_firmware"),
                            "channels": device.get("channels")}}
    except SessionFailure as exc:
        return {"connected": False, "ready": False, "backend": "native-session",
                "error_code": exc.code, "message": str(exc)}


def _is_retryable_open_error(message: str) -> bool:
    return _RETRYABLE_OPEN_FRAGMENT in (message or "").lower()


def status() -> dict[str, Any]:
    cli = find_native_cli()
    if cli is None:
        return {"connected": False, "ready": False, "error_code": "CLI_MISSING",
                "message": "Run scripts/bootstrap-native.ps1 and set DL16_CLI_PATH if needed"}
    if _session_enabled():
        return _session_status(cli)
    return _status_once(cli)


def _backoff_seconds(attempt: int) -> float:
    """Linear backoff after the given 1-based failed attempt (0.5 s, 1.0 s, ...)."""
    return 0.5 * attempt


def _status_once(cli: Path) -> dict[str, Any]:
    last_msg = ""
    retry_log: list[dict[str, Any]] = []
    attempt = 0
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            r = subprocess.run([str(cli), "info"], capture_output=True, text=True, timeout=10, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"connected": False, "ready": False, "error_code": "CLI_ERROR", "message": str(exc),
                    "attempts": attempt, "retry_log": retry_log}
        if r.returncode == 0:
            fields = {}
            for line in r.stdout.splitlines():
                if ":" in line:
                    key, value = line.split(":", 1)
                    fields[re.sub(r"\s+", "_", key.strip().lower())] = value.strip()
            return {"connected": True, "ready": True, "cli_path": str(cli), "details": fields,
                    "attempts": attempt, "retry_log": retry_log}
        last_msg = (r.stderr or r.stdout).strip()[-1500:]
        # The pinned backend's FPGA device-info query deterministically fails once
        # immediately after a completed capture (see DL16-TASK-002 B6). Retrying the
        # read-only CLI invocation recovers; this is not a USB reset.
        if attempt < MAX_ATTEMPTS and _is_retryable_open_error(last_msg):
            retry_log.append({"attempt": attempt, "error": last_msg[-200:]})
            _sleep(_backoff_seconds(attempt))
            continue
        break
    return {"connected": False, "ready": False, "error_code": "DEVICE_OR_DRIVER_ERROR", "message": last_msg,
            "attempts": attempt, "retry_log": retry_log}


def capture(request: CaptureRequest, timeout_s: float = 45.0,
            trigger_position_percent: float | None = None,
            trigger_timeout_sec: int | None = None,
            raw_rx_path: str | Path | None = None,
            raw_rx_max_bytes: int = 32 * 1024 * 1024) -> dict[str, Any]:
    try:
        request.validate()
        if raw_rx_path is not None:
            path = Path(raw_rx_path)
            if (not path.is_absolute() or path.exists() or path.is_symlink()
                    or not path.parent.is_dir() or "\x00" in str(path)
                    or (os.name == "nt" and (":" in str(path)[2:] or str(path).startswith("\\\\")))):
                raise ValueError("raw_rx_path must be a new absolute local file in an existing directory")
            if type(raw_rx_max_bytes) is not int or not 8 <= raw_rx_max_bytes <= 32 * 1024 * 1024:
                raise ValueError("raw_rx_max_bytes must be 8..33554432")
            raw_rx_path = str(path)
        elif raw_rx_max_bytes != 32 * 1024 * 1024:
            raise ValueError("raw_rx_max_bytes requires raw_rx_path")
        if request.rle:
            return {"success": False, "error_code": "RLE_NOT_VALIDATED",
                    "evidence_source": "NONE", "data_integrity": "UNKNOWN",
                    "message": "Hardware RLE framing and bounded expansion are not validated; request not sent"}
        if not 1.0 <= timeout_s <= 3600:
            raise ValueError("timeout_s must be from 1 to 3600 seconds")
        if trigger_position_percent is not None and not 0.0 <= trigger_position_percent <= 100.0:
            raise ValueError("trigger_position_percent must be within [0, 100]")
        if trigger_timeout_sec is not None and not 1 <= trigger_timeout_sec <= 3600:
            raise ValueError("trigger_timeout_sec must be from 1 to 3600")
        # An explicit device wait must fit inside the host deadline with transfer/cleanup slack.
        if (request.trigger != "immediate" and trigger_timeout_sec is not None
                and timeout_s <= trigger_timeout_sec + request.duration_ms / 1000 + 5):
            raise ValueError("Host timeout must exceed trigger wait + capture duration + 5s cleanup margin")
    except (ValueError, TypeError) as exc:
        return {"success": False, "error_code": "INVALID_CAPTURE_CONFIG", "message": str(exc),
                "data_integrity": "UNKNOWN", "evidence_source": "NONE"}

    cli = find_native_cli()
    if cli is None:
        return {"success": False, "error_code": "CLI_MISSING", "evidence_source": "NONE",
                "data_integrity": "UNKNOWN", "message": "Native binary is not installed"}
    raw_options: dict[str, Any] = {}
    if raw_rx_path is not None:
        try:
            probe = subprocess.run([str(cli), "capabilities"], capture_output=True,
                                   text=True, timeout=5, check=False)
            if probe.returncode != 0 or json.loads(probe.stdout).get("raw_rx_log") != "dl16-raw-rx/v1":
                raise ValueError("native binary does not advertise raw RX logging v1")
        except (OSError, subprocess.TimeoutExpired, ValueError, AttributeError) as exc:
            return {"success": False, "error_code": "RAW_RX_UNSUPPORTED", "message": str(exc),
                    "data_integrity": "UNKNOWN", "evidence_source": "NONE"}
        raw_options = {"raw_rx_path": raw_rx_path, "raw_rx_max_bytes": raw_rx_max_bytes}
    if _session_enabled():
        try:
            response = _get_session(cli).request({
                **raw_options,
                "command": "capture",
                "channels": list(request.channels),
                "sample_rate_hz": request.sample_rate_hz,
                "duration_ms": request.duration_ms,
                "threshold_voltage": request.threshold_voltage,
                "trigger": request.trigger,
                "trigger_position_percent": (trigger_position_percent if trigger_position_percent is not None else 10.0),
                "trigger_timeout_sec": (trigger_timeout_sec if trigger_timeout_sec is not None else 30),
                "output_dir": str(captures_dir()),
            }, timeout_s=timeout_s)
            doc = response.get("result")
            if not isinstance(doc, dict):
                raise SessionFailure("SESSION_PROTOCOL_ERROR", "capture response missing result object")
            if doc.get("success") and (doc.get("data_integrity") != "COMPLETE" or
                                        not doc.get("capture_complete_received") or
                                        not doc.get("trigger_ack_received")):
                doc["success"] = False
                doc["error_code"] = "EVIDENCE_INCOMPLETE"
                doc["message"] = "Capture finished without required integrity markers"
            if not doc.get("success"):
                # An incomplete or timed-out acquisition cannot safely reuse device state.
                session = _get_session(cli)
                try:
                    session.close()
                    doc["session_cleanup"] = "closed"
                except SessionFailure as cleanup:
                    doc["session_cleanup"] = {"error_code": cleanup.code, "message": str(cleanup)}
                with _SESSION_LOCK:
                    global _SESSION, _SESSION_PATH
                    if _SESSION is session:
                        _SESSION = None
                        _SESSION_PATH = None
                doc["session_invalidated"] = True
            doc["backend"] = "native-session"
            doc["attempts"] = 1
            doc["retry_log"] = []
            doc["warnings"] = list(doc.get("warnings") or [])
            return doc
        except SessionFailure as exc:
            return {"success": False, "error_code": exc.code, "message": str(exc),
                    "data_integrity": "UNKNOWN", "evidence_source": "NONE",
                    "backend": "native-session", "attempts": 1, "retry_log": [],
                    "session_diagnostics": getattr(exc, "diagnostics", None)}
    cmd = [str(cli), "capture", "--channels", ",".join(map(str, request.channels)),
           "--sample-rate", str(request.sample_rate_hz), "--duration", f"{request.duration_ms}ms",
           "--threshold", str(request.threshold_voltage), "--trigger", request.trigger,
           "--mode", request.mode, "--out", str(captures_dir()), "--json"]
    if raw_options:
        cmd += ["--raw-rx-path", str(raw_rx_path), "--raw-rx-max-bytes", str(raw_rx_max_bytes)]
    if trigger_position_percent is not None:
        cmd += ["--trigger-position", str(trigger_position_percent)]
    if trigger_timeout_sec is not None:
        cmd += ["--trigger-timeout", str(trigger_timeout_sec)]
    last_doc: dict[str, Any] | None = None
    retry_log: list[dict[str, Any]] = []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            # Upstream CLI runs a fixed 30 s device watchdog; process timeout is separate.
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s, check=False)
        except subprocess.TimeoutExpired:
            return {"success": False, "error_code": "HOST_TIMEOUT", "data_integrity": "UNKNOWN",
                    "evidence_source": "NONE", "message": "Native CLI killed after host timeout; reset device state before retry"}
        except OSError as exc:
            return {"success": False, "error_code": "CLI_EXEC_ERROR", "data_integrity": "UNKNOWN",
                    "evidence_source": "NONE", "message": str(exc)}
        try:
            doc = json.loads(r.stdout)
            if not isinstance(doc, dict):
                raise ValueError("CLI JSON must be an object")
        except (ValueError, json.JSONDecodeError):
            return {"success": False, "error_code": "CLI_OUTPUT_INVALID", "evidence_source": "NONE",
                    "data_integrity": "UNKNOWN", "message": (r.stderr or r.stdout)[-2000:]}
        if r.returncode != 0:
            doc["success"] = False
            doc.setdefault("error_code", "CLI_CAPTURE_FAILED")
        # Do not fabricate evidence metadata when CLI fails.
        if doc.get("success") and (doc.get("data_integrity") != "COMPLETE" or not doc.get("capture_complete_received") or not doc.get("trigger_ack_received")):
            doc["success"] = False
            doc["error_code"] = "EVIDENCE_INCOMPLETE"
            doc["message"] = "Capture finished without required integrity markers"
        # Retry only the deterministic post-capture device-info open failure
        # (DL16-TASK-002 B6); never retry a timeout or an incomplete evidence result.
        if (not doc.get("success") and attempt < MAX_ATTEMPTS
                and _is_retryable_open_error(str(doc.get("message", "")))):
            retry_log.append({"attempt": attempt, "error_code": doc.get("error_code"),
                              "message": str(doc.get("message", ""))[-200:]})
            last_doc = doc
            _sleep(_backoff_seconds(attempt))
            continue
        doc["backend"] = "native-cli"
        doc["attempts"] = attempt
        doc["retry_log"] = retry_log
        if retry_log:
            doc.setdefault("warnings", []).append(
                f"open-retry: {len(retry_log)} retried attempt(s) after post-capture device-info failure")
        return doc
    assert last_doc is not None
    last_doc["backend"] = "native-cli"
    last_doc["attempts"] = MAX_ATTEMPTS
    last_doc["retry_log"] = retry_log
    last_doc.setdefault("warnings", []).append(
        f"open-retry exhausted after {MAX_ATTEMPTS} attempts")
    return last_doc


def pwm(output: int, action: str = "configure", frequency_hz: int = 1000,
        duty_percent: float = 50.0, confirm_safe_wiring: bool = False) -> dict[str, Any]:
    import math
    if not confirm_safe_wiring:
        return {"success": False, "error_code": "PWM_CONFIRMATION_REQUIRED",
                "message": "Explicit safe output wiring/voltage confirmation required"}
    if (type(output) is not int or output not in (0, 1) or action not in ("configure", "stop")
            or (action == "configure" and (type(frequency_hz) is not int or not 1 <= frequency_hz <= 20000000
                or isinstance(duty_percent, bool) or not isinstance(duty_percent, (int, float))
                or not math.isfinite(duty_percent) or not 0 <= duty_percent <= 100))):
        return {"success": False, "error_code": "INVALID_PWM"}
    if not _session_enabled():
        return {"success": False, "error_code": "SESSION_MODE_REQUIRED",
                "message": "PWM requires explicit session backend for single-owner configuration/capture"}
    cli = find_native_cli()
    if cli is None:
        return {"success": False, "error_code": "CLI_MISSING"}
    request = {"command": "pwm", "op": action, "output": output}
    if action == "configure":
        request.update(frequency_hz=frequency_hz, duty_percent=duty_percent)
    try:
        response = _get_session(cli).request(request, timeout_s=10)
        return {"success": True, "backend": "native-session", "response": response,
                "physical_output_verified": False}
    except SessionFailure as exc:
        return {"success": False, "error_code": exc.code, "message": str(exc)}


def close_session() -> dict[str, Any]:
    global _SESSION, _SESSION_PATH
    with _SESSION_LOCK:
        session, _SESSION = _SESSION, None
        _SESSION_PATH = None
    if session is None:
        return {"success": True, "closed": False}
    try:
        session.close()
        return {"success": True, "closed": True}
    except SessionFailure as exc:
        return {"success": False, "closed": True, "error_code": exc.code, "message": str(exc)}


def stream_start(*, experimental_opt_in: bool = False, safety_confirmation: str = "",
                 channels: list[int] | None = None, sample_rate_hz: int = 20_000_000,
                 duration_ms: int = 20, threshold_voltage: float = 1.6,
                       raw_rx_logging: bool = False, raw_rx_max_bytes: int = 33_554_432) -> dict[str, Any]:
    """Experimental uncropped Stream; never returns trusted waveform data."""
    if experimental_opt_in is not True:
        return {"success": False, "error_code": "EXPERIMENTAL_OPT_IN_REQUIRED", "stream_available": False}
    try:
        if safety_confirmation != "CONFIRMED_SAFE_WIRING_GUI_CLOSED":
            raise ValueError("Explicit safe wiring/threshold and GUI-closed confirmation required")
        if type(raw_rx_logging) is not bool or type(raw_rx_max_bytes) is not int or not 8 <= raw_rx_max_bytes <= 33_554_432:
            raise ValueError("Invalid bounded raw RX logging configuration")
        raw_budget = raw_rx_max_bytes if raw_rx_logging else 0
        request = CaptureRequest(tuple(channels or []), sample_rate_hz, duration_ms, threshold_voltage)
        request.validate()
        if (len(request.channels) > 2 or sample_rate_hz not in (1_000_000, 2_000_000, 4_000_000, 5_000_000, 10_000_000, 20_000_000)
                or duration_ms > 30_000 or ((sample_rate_hz * duration_ms // 1000 + 7) // 8) * 16 + 1_048_576 + raw_budget > 200 * 1024 * 1024):
            raise ValueError("Experimental Stream exceeds all16 budget/rate/duration bounds")
        if not _session_enabled():
            raise ValueError("Experimental Stream requires DL16_BACKEND_MODE=session")
        cli = find_native_cli()
        if cli is None:
            raise ValueError("Native CLI unavailable")
        import uuid
        directory = captures_dir() / ("experimental-stream-" + uuid.uuid4().hex)
        return _get_session(cli).request({"command": "stream_start", "experimental_opt_in": True,
            "safety_confirmation": safety_confirmation, "channels": list(request.channels),
            "sample_rate_hz": sample_rate_hz, "duration_ms": duration_ms,
            "threshold_voltage": threshold_voltage, "output_dir": str(directory.resolve()),
            **({"raw_rx_logging": True, "raw_rx_max_bytes": raw_rx_max_bytes} if raw_rx_logging else {})}, timeout_s=5)
    except (ValueError, SessionFailure) as exc:
        return {"success": False, "error_code": getattr(exc, "code", "INVALID_STREAM"), "message": str(exc)}


def stream_control(operation_id: str, *, cancel: bool = False) -> dict[str, Any]:
    with _SESSION_LOCK:
        session = _SESSION
    if session is None or session.failed or not _session_enabled():
        return {"success": False, "error_code": "NO_ACTIVE_SESSION", "message": "Original owner unavailable"}
    try:
        return session.request({"command": "stream_cancel" if cancel else "stream_poll",
                                "operation_id": operation_id}, timeout_s=5)
    except SessionFailure as exc:
        return {"success": False, "error_code": exc.code, "message": str(exc)}


def buffer_start(request: CaptureRequest, trigger_timeout_sec: int = 30) -> dict[str, Any]:
    """Start opt-in bounded BUFFER; never advertise or silently select Stream."""
    try:
        request.validate()
        if (len(request.channels) > 2 or request.sample_rate_hz > 20_000_000
                or request.duration_ms > 30_000 or request.trigger != "immediate" or request.rle
                or type(trigger_timeout_sec) is not int or not 1 <= trigger_timeout_sec <= 30):
            raise ValueError("Async BUFFER requires <=2 channels, <=20MHz, <=30s, immediate, no RLE")
        if not _session_enabled():
            raise ValueError("Async BUFFER requires DL16_BACKEND_MODE=session")
        cli = find_native_cli()
        if cli is None:
            raise ValueError("Native CLI unavailable")
        return _get_session(cli).request({"command": "capture_start", "channels": list(request.channels),
            "sample_rate_hz": request.sample_rate_hz, "duration_ms": request.duration_ms,
            "threshold_voltage": request.threshold_voltage, "trigger": "immediate",
            "trigger_timeout_sec": trigger_timeout_sec, "output_dir": str(captures_dir())}, timeout_s=5)
    except (ValueError, SessionFailure) as exc:
        return {"success": False, "error_code": getattr(exc, "code", "INVALID_CAPTURE"), "message": str(exc)}


def buffer_control(operation_id: str, *, cancel: bool = False) -> dict[str, Any]:
    # Never create/restart a worker to poll an operation belonging to a lost owner.
    with _SESSION_LOCK:
        session = _SESSION
    if session is None or session.failed or not _session_enabled():
        return {"success": False, "error_code": "NO_ACTIVE_SESSION", "message": "Original owner unavailable"}
    try:
        response = session.request({"command": "capture_cancel" if cancel else "capture_poll",
                                    "operation_id": operation_id}, timeout_s=5)
        nested = response.get("response", {}).get("result")
        if isinstance(nested, dict) and nested.get("success") is True and (
                nested.get("data_integrity") != "COMPLETE" or not nested.get("trigger_ack_received")
                or not nested.get("capture_complete_received")):
            nested["success"] = False
            nested["error_code"] = "INCOMPLETE_CAPTURE"
        return response
    except SessionFailure as exc:
        return {"success": False, "error_code": exc.code, "message": str(exc)}
