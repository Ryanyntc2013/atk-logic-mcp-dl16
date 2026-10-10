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
from typing import Any

from .config import CaptureRequest, captures_dir


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


def status() -> dict[str, Any]:
    cli = find_native_cli()
    if cli is None:
        return {"connected": False, "ready": False, "error_code": "CLI_MISSING",
                "message": "Run scripts/bootstrap-native.ps1 and set DL16_CLI_PATH if needed"}
    try:
        r = subprocess.run([str(cli), "info"], capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"connected": False, "ready": False, "error_code": "CLI_ERROR", "message": str(exc)}
    if r.returncode != 0:
        return {"connected": False, "ready": False, "error_code": "DEVICE_OR_DRIVER_ERROR",
                "message": (r.stderr or r.stdout).strip()[-1500:]}
    fields = {}
    for line in r.stdout.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            fields[re.sub(r"\s+", "_", key.strip().lower())] = value.strip()
    return {"connected": True, "ready": True, "cli_path": str(cli), "details": fields}


def capture(request: CaptureRequest, timeout_s: float = 45.0) -> dict[str, Any]:
    try:
        request.validate()
        if not 1.0 <= timeout_s <= 3600:
            raise ValueError("timeout_s must be from 1 to 3600 seconds")
    except (ValueError, TypeError) as exc:
        return {"success": False, "error_code": "INVALID_CAPTURE_CONFIG", "message": str(exc),
                "data_integrity": "UNKNOWN", "evidence_source": "NONE"}

    cli = find_native_cli()
    if cli is None:
        return {"success": False, "error_code": "CLI_MISSING", "evidence_source": "NONE",
                "data_integrity": "UNKNOWN", "message": "Native binary is not installed"}
    cmd = [str(cli), "capture", "--channels", ",".join(map(str, request.channels)),
           "--sample-rate", str(request.sample_rate_hz), "--duration", f"{request.duration_ms}ms",
           "--threshold", str(request.threshold_voltage), "--trigger", request.trigger,
           "--mode", request.mode, "--out", str(captures_dir()), "--json"]
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
    doc["backend"] = "native-cli"
    return doc
