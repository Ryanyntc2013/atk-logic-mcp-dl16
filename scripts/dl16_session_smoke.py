#!/usr/bin/env python3
"""Bounded two-request session smoke test harness for DL16-TASK-021.

Prepares and runs an auditable two-request session smoke test on ATK-DL16.
Default mode is offline dry-run (prints plan and configuration without launching child).
Live execution requires explicit CLI confirmation flags for:
  - connected device
  - safe wiring (PWM0 -> CH8, PWM1 -> CH14, shared GND)
  - safe signal voltage
  - signal source already configured and operating

This script NEVER configures PWM, alters GPIOs, or resets hardware.
All capture outputs and step-by-step JSON responses are durably recorded
into a unique per-run evidence folder under the specified operator task directory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import uuid
from typing import Any, Callable

# Ensure dl16_mcp package can be imported when run directly from scripts/
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from dl16_mcp.backend import find_native_cli  # noqa: E402
from dl16_mcp.session import NativeSession, SessionFailure  # noqa: E402


TARGET_CHANNELS = [8, 14]
TARGET_SAMPLE_RATE_HZ = 20_000_000
TARGET_DURATION_MS = 10
TARGET_THRESHOLD_VOLTS = 1.6
TARGET_TRIGGER = "immediate"
EXPECTED_SAMPLES_PER_CHANNEL = 200_000  # (20_000_000 * 10) / 1000


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="DL16-TASK-021 bounded two-request session smoke harness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--taskdir",
        type=Path,
        required=True,
        help="Base operator task directory (e.g. artifacts/hil/DL16-TASK-021)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        default=False,
        help="Opt-in to real live session execution (default: offline dry-run)",
    )
    parser.add_argument(
        "--confirm-connected",
        action="store_true",
        default=False,
        help="Confirm DL16 hardware is physically connected via USB",
    )
    parser.add_argument(
        "--confirm-wiring",
        action="store_true",
        default=False,
        help="Confirm safe wiring on CH8 and CH14 with shared GND",
    )
    parser.add_argument(
        "--confirm-voltage",
        action="store_true",
        default=False,
        help="Confirm signal voltage is safe for DL16 inputs (<= 3.3V CMOS)",
    )
    parser.add_argument(
        "--confirm-signal-configured",
        action="store_true",
        default=False,
        help="Confirm signal state/source is acknowledged by operator (or explicitly unverified; harness will not set PWM or reset)",
    )
    parser.add_argument(
        "--source-declaration",
        type=str,
        default="",
        help="Human/operator declaration of signal source (required for live execution)",
    )
    parser.add_argument(
        "--cli-path",
        type=Path,
        default=None,
        help="Optional explicit path to atk-dl16 executable",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=45.0,
        help="Per-request capture timeout in seconds (default: 45.0)",
    )
    return parser


def durable_write_json(file_path: Path, data: dict[str, Any]) -> None:
    """Atomically write and fsync JSON data to disk. Fails closed on any error."""
    payload = json.dumps(data, indent=2, ensure_ascii=False)
    temp_path = file_path.with_suffix(".tmp")
    with open(temp_path, "w", encoding="utf-8") as f:
        f.write(payload)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp_path, file_path)


def _safe_int_key(key: Any) -> int | None:
    """Safely convert a channel key to int without throwing on non-numeric types."""
    if isinstance(key, int):
        return key
    if isinstance(key, str):
        try:
            return int(key)
        except (ValueError, TypeError):
            return None
    return None


def inspect_capture_validity(response_result: dict[str, Any], artifact_meta: dict[str, Any]) -> dict[str, Any]:
    """Inspect native response and saved capture meta.json against TASK-021 criteria.

    Returns a dict with 'valid': bool, 'reasons': list[str], and summary fields.
    Refuses ambiguous or non-dict schemas fail-closed.
    Native hardware sample_counts transmits all 16 channels, while channels field
    controls requested configuration. We verify exactly channels [8, 14] and that
    counts on channels 8 and 14 match EXPECTED_SAMPLES_PER_CHANNEL without crashing
    on invalid key types.
    """
    reasons: list[str] = []
    if not isinstance(response_result, dict):
        return {"valid": False, "reasons": ["response_result is not a dict"]}
    if not isinstance(artifact_meta, dict):
        return {"valid": False, "reasons": ["artifact_meta is not a dict"]}

    # 1. Native response level
    if response_result.get("success") is not True:
        reasons.append(f"response success is not True: {response_result.get('success')}")
    if response_result.get("data_integrity") != "COMPLETE":
        reasons.append(f"response data_integrity != COMPLETE: {response_result.get('data_integrity')}")
    if response_result.get("capture_complete_received") is not True:
        reasons.append("response capture_complete_received is not True")
    if response_result.get("trigger_ack_received") is not True:
        reasons.append("response trigger_ack_received is not True")

    # Native response samples: actual_samples_per_channel contains requested channels
    resp_counts = response_result.get("actual_samples_per_channel")
    if not isinstance(resp_counts, dict):
        reasons.append("response actual_samples_per_channel is missing or not a dict")
    else:
        # Validate keys type-safely
        resp_channel_map: dict[int, Any] = {}
        for k, v in resp_counts.items():
            parsed_k = _safe_int_key(k)
            if parsed_k is None:
                reasons.append(f"response actual_samples_per_channel contains non-integer channel key: {k!r}")
            else:
                resp_channel_map[parsed_k] = v

        resp_channels = sorted(resp_channel_map.keys())
        if resp_channels != sorted(TARGET_CHANNELS):
            reasons.append(f"response actual_samples_per_channel keys {resp_channels} != {TARGET_CHANNELS}")
        for ch in TARGET_CHANNELS:
            cnt = resp_channel_map.get(ch)
            if cnt != EXPECTED_SAMPLES_PER_CHANNEL:
                reasons.append(f"response channel {ch} samples {cnt} != expected {EXPECTED_SAMPLES_PER_CHANNEL}")

    # 2. Meta.json level
    if artifact_meta.get("data_integrity") != "COMPLETE":
        reasons.append(f"meta data_integrity != COMPLETE: {artifact_meta.get('data_integrity')}")
    if artifact_meta.get("capture_complete_received") is not True:
        reasons.append("meta capture_complete_received is not True")
    if artifact_meta.get("trigger_ack_received") is not True:
        reasons.append("meta trigger_ack_received is not True")

    meta_channels = artifact_meta.get("channels")
    if not isinstance(meta_channels, list):
        reasons.append(f"meta channels is not a list: {type(meta_channels).__name__}")
    else:
        parsed_meta_channels = []
        for ch in meta_channels:
            p_ch = _safe_int_key(ch)
            if p_ch is None:
                reasons.append(f"meta channels contains non-integer element: {ch!r}")
            else:
                parsed_meta_channels.append(p_ch)
        if sorted(parsed_meta_channels) != sorted(TARGET_CHANNELS):
            reasons.append(f"meta channels {parsed_meta_channels} != {TARGET_CHANNELS}")

    # meta.json sample_counts may include all 16 channels from hardware transmission;
    # verify target channels exist and match expected count, and all keys are safe integers.
    meta_counts = artifact_meta.get("sample_counts")
    if not isinstance(meta_counts, dict):
        reasons.append("meta sample_counts is missing or not a dict")
    else:
        meta_counts_map: dict[int, Any] = {}
        for k, v in meta_counts.items():
            parsed_k = _safe_int_key(k)
            if parsed_k is None:
                reasons.append(f"meta sample_counts contains non-integer key: {k!r}")
            else:
                meta_counts_map[parsed_k] = v

        for ch in TARGET_CHANNELS:
            if ch not in meta_counts_map:
                reasons.append(f"meta sample_counts missing target channel {ch}")
            else:
                cnt = meta_counts_map[ch]
                if cnt != EXPECTED_SAMPLES_PER_CHANNEL:
                    reasons.append(f"meta channel {ch} samples {cnt} != expected {EXPECTED_SAMPLES_PER_CHANNEL}")

    sr = artifact_meta.get("sample_rate")
    if sr != TARGET_SAMPLE_RATE_HZ:
        reasons.append(f"meta sample_rate {sr} != {TARGET_SAMPLE_RATE_HZ}")

    dur = artifact_meta.get("duration_ms")
    if dur != TARGET_DURATION_MS:
        reasons.append(f"meta duration_ms {dur} != {TARGET_DURATION_MS}")

    return {
        "valid": len(reasons) == 0,
        "reasons": reasons,
        "exact_channels": TARGET_CHANNELS,
        "expected_samples_per_channel": EXPECTED_SAMPLES_PER_CHANNEL,
    }


def execute_session_smoke(
    taskdir: Path,
    live: bool,
    confirm_connected: bool,
    confirm_wiring: bool,
    confirm_voltage: bool,
    confirm_signal_configured: bool,
    source_declaration: str = "",
    cli_path: Path | None = None,
    timeout_s: float = 45.0,
    session_factory: Callable[[Path], NativeSession] | None = None,
) -> dict[str, Any]:
    """Execute dry-run or live bounded two-request session smoke."""
    taskdir = Path(taskdir).resolve()

    plan = {
        "task": "DL16-TASK-021",
        "scope": "bounded two-request session smoke",
        "channels": TARGET_CHANNELS,
        "sample_rate_hz": TARGET_SAMPLE_RATE_HZ,
        "duration_ms": TARGET_DURATION_MS,
        "threshold_volts": TARGET_THRESHOLD_VOLTS,
        "trigger": TARGET_TRIGGER,
        "expected_samples_per_channel": EXPECTED_SAMPLES_PER_CHANNEL,
        "live": live,
        "source_declaration": source_declaration or "(none declared)",
    }

    # If dry-run (offline default), do not require hardware confirmation flags
    # and do not launch binary/USB. Simply output configuration.
    if not live:
        return {
            "status": "DRY_RUN",
            "message": "Dry-run offline mode. No child process or hardware operations invoked.",
            "plan": plan,
            "required_confirmations_for_live": [
                "--live",
                "--confirm-connected",
                "--confirm-wiring",
                "--confirm-voltage",
                "--confirm-signal-configured",
            ],
        }

    # Live opt-in: check all required safety gates strictly
    missing_confirmations = []
    if not confirm_connected:
        missing_confirmations.append("confirm_connected")
    if not confirm_wiring:
        missing_confirmations.append("confirm_wiring (PWM0->CH8, PWM1->CH14, GND)")
    if not confirm_voltage:
        missing_confirmations.append("confirm_voltage (<= 3.3V CMOS)")
    if not confirm_signal_configured:
        missing_confirmations.append("confirm_signal_configured (signal state acknowledged/unverified)")
    if not source_declaration or not source_declaration.strip():
        missing_confirmations.append("source_declaration (non-empty description required)")

    if missing_confirmations:
        return {
            "status": "REFUSED_MISSING_CONFIRMATION",
            "message": f"Refusing live execution. Missing required confirmations: {', '.join(missing_confirmations)}",
            "missing_confirmations": missing_confirmations,
            "plan": plan,
        }

    # Locate executable
    exe = cli_path or find_native_cli()
    if exe is None or not Path(exe).is_file():
        return {
            "status": "CLI_MISSING",
            "message": f"Native CLI executable not found: {exe}",
            "plan": plan,
        }
    exe = Path(exe).resolve()

    # Compute binary sha256
    try:
        binary_sha256 = hashlib.sha256(exe.read_bytes()).hexdigest()
    except OSError as exc:
        return {
            "status": "CLI_UNREADABLE",
            "message": f"Failed reading native CLI executable for hashing: {exc}",
            "plan": plan,
        }

    # Prepare unique per-run evidence directory with UUID under taskdir
    run_timestamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    unique_run_id = f"smoke-{run_timestamp}-{uuid.uuid4().hex}"
    run_dir = taskdir / unique_run_id
    captures_output_dir = run_dir / "captures"
    journal_dir = run_dir / "journal"

    try:
        run_dir.mkdir(parents=True, exist_ok=False)
        captures_output_dir.mkdir(parents=True, exist_ok=True)
        journal_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return {
            "status": "DIR_CREATION_FAILED",
            "message": f"Failed creating unique run directory {run_dir}: {exc}",
            "plan": plan,
        }

    bundle: dict[str, Any] = {
        "task_id": "DL16-TASK-021",
        "run_id": unique_run_id,
        "run_dir": str(run_dir),
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "native_cli": {
            "path": str(exe),
            "sha256": binary_sha256,
        },
        "source_declaration": {
            "declared_text": source_declaration,
            "authority": "caller_declared_unverified",
            "physical_proof": False,
        },
        "steps": [],
        "cleanup": {},
        "verdict": "UNKNOWN",
    }

    # Helper to write bundle safely to disk
    bundle_file = run_dir / "smoke_bundle.json"

    # Configure session journal directory for the child process via environment
    orig_journal_dir = os.environ.get("DL16_SESSION_JOURNAL_DIR")
    os.environ["DL16_SESSION_JOURNAL_DIR"] = str(journal_dir)

    session: NativeSession | None = None
    session_construction_error = False

    try:
        # Construct session; record any constructor exception in bundle
        try:
            if session_factory is not None:
                session = session_factory(exe)
            else:
                session = NativeSession(exe)
        except Exception as init_exc:
            session_construction_error = True
            bundle["constructor_error"] = str(init_exc)
            bundle["verdict"] = "SESSION_INIT_FAILED"

        if not session_construction_error and session is not None:
            # We execute up to two capture requests in this single session
            for step_idx in (1, 2):
                step_file = run_dir / f"step_{step_idx}.json"
                step_record: dict[str, Any] = {
                    "step": step_idx,
                    "request_params": {
                        "command": "capture",
                        "channels": TARGET_CHANNELS,
                        "sample_rate_hz": TARGET_SAMPLE_RATE_HZ,
                        "duration_ms": TARGET_DURATION_MS,
                        "threshold_voltage": TARGET_THRESHOLD_VOLTS,
                        "trigger": TARGET_TRIGGER,
                        "trigger_position_percent": 10.0,
                        "trigger_timeout_sec": 30,
                        "output_dir": str(captures_output_dir),
                    },
                    "status": "DISPATCHING",
                    "dispatch_timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }

                # CRITICAL: Durable write BEFORE dispatch
                try:
                    durable_write_json(step_file, step_record)
                except OSError as write_exc:
                    step_record["status"] = "PRE_DISPATCH_WRITE_FAILED"
                    step_record["error"] = str(write_exc)
                    bundle["steps"].append(step_record)
                    bundle["verdict"] = "EVIDENCE_WRITE_FAILED"
                    # Write failure stops next request & fails closed
                    break

                try:
                    started_t = time.monotonic()
                    raw_response = session.request(step_record["request_params"], timeout_s=timeout_s)
                    elapsed_s = time.monotonic() - started_t
                    step_record["elapsed_seconds"] = elapsed_s
                    step_record["raw_response"] = raw_response

                    if not raw_response.get("ok"):
                        step_record["status"] = "NATIVE_COMMAND_FAILED"
                        step_record["error"] = raw_response.get("message", "unknown error")
                        bundle["steps"].append(step_record)
                        bundle["verdict"] = "FIRST_REQUEST_FAILED" if step_idx == 1 else "SECOND_REQUEST_FAILED"
                    else:
                        res = raw_response.get("result")
                        if not isinstance(res, dict):
                            step_record["status"] = "MALFORMED_RESULT"
                            step_record["error"] = "Response 'result' is not a dictionary"
                            bundle["steps"].append(step_record)
                            bundle["verdict"] = "FIRST_REQUEST_FAILED" if step_idx == 1 else "SECOND_REQUEST_FAILED"
                        else:
                            # Locate saved capture metadata
                            capture_id = res.get("capture_id")
                            artifact_dir = res.get("artifact_dir")
                            meta_path = None
                            if artifact_dir and Path(artifact_dir).is_dir():
                                meta_path = Path(artifact_dir) / "meta.json"
                            elif capture_id and (captures_output_dir / capture_id).is_dir():
                                meta_path = captures_output_dir / capture_id / "meta.json"

                            artifact_meta: dict[str, Any] = {}
                            if meta_path and meta_path.is_file():
                                try:
                                    artifact_meta = json.loads(meta_path.read_text(encoding="utf-8"))
                                except Exception as meta_exc:
                                    step_record["meta_read_error"] = str(meta_exc)
                            else:
                                step_record["meta_path_missing"] = str(meta_path)

                            step_record["artifact_meta"] = artifact_meta

                            # Strict verification
                            validity = inspect_capture_validity(res, artifact_meta)
                            step_record["validity"] = validity

                            if not validity["valid"]:
                                step_record["status"] = "CAPTURE_CRITERIA_MISMATCH"
                                step_record["reasons"] = validity["reasons"]
                                bundle["steps"].append(step_record)
                                bundle["verdict"] = "FIRST_REQUEST_FAILED" if step_idx == 1 else "SECOND_REQUEST_FAILED"
                            else:
                                step_record["status"] = "STEP_SUCCESS"
                                bundle["steps"].append(step_record)

                except SessionFailure as exc:
                    step_record["status"] = "SESSION_FAILURE"
                    step_record["error_code"] = exc.code
                    step_record["message"] = str(exc)
                    step_record["diagnostics"] = getattr(exc, "diagnostics", None)
                    bundle["steps"].append(step_record)
                    bundle["verdict"] = "FIRST_REQUEST_FAILED" if step_idx == 1 else "SECOND_REQUEST_FAILED"
                except Exception as exc:
                    step_record["status"] = "UNEXPECTED_EXCEPTION"
                    step_record["message"] = str(exc)
                    bundle["steps"].append(step_record)
                    bundle["verdict"] = "FIRST_REQUEST_FAILED" if step_idx == 1 else "SECOND_REQUEST_FAILED"

                # CRITICAL: Durable write AFTER completion/error
                try:
                    durable_write_json(step_file, step_record)
                except OSError as write_exc:
                    step_record["post_dispatch_write_error"] = str(write_exc)
                    bundle["verdict"] = "EVIDENCE_WRITE_FAILED"
                    # Write failure stops any subsequent request
                    break

                # If this step was not a success, stop loop immediately
                if step_record.get("status") != "STEP_SUCCESS":
                    break

            # Check overall verdict after loop
            if len(bundle["steps"]) == 2 and all(s.get("status") == "STEP_SUCCESS" for s in bundle["steps"]):
                bundle["verdict"] = "CAPTURE_VALIDITY_PASS"
                bundle["notes"] = (
                    "Both requests satisfied exact channel and sample count criteria with complete ACK integrity. "
                    "Waveform contents were NOT evaluated and physical provenance is uncertified."
                )

    finally:
        # ALWAYS close owned session in finally
        cleanup_outcome: dict[str, Any] = {"session_closed": False}
        if session is not None:
            try:
                session.close()
                cleanup_outcome["session_closed"] = True
            except Exception as clean_exc:
                cleanup_outcome["session_closed"] = False
                cleanup_outcome["clean_error"] = str(clean_exc)
        else:
            cleanup_outcome["session_closed"] = True
            cleanup_outcome["note"] = "session was never started or constructed"

        bundle["cleanup"] = cleanup_outcome

        # CRITICAL: Cleanup failure overrides CAPTURE_VALIDITY_PASS
        if not cleanup_outcome["session_closed"]:
            bundle["verdict"] = "CLEANUP_FAILED"

        # Restore environment variable
        if orig_journal_dir is None:
            os.environ.pop("DL16_SESSION_JOURNAL_DIR", None)
        else:
            os.environ["DL16_SESSION_JOURNAL_DIR"] = orig_journal_dir

        # Persist complete evidence bundle JSON to disk with fsync
        try:
            durable_write_json(bundle_file, bundle)
        except OSError as exc:
            bundle["bundle_write_error"] = str(exc)
            bundle["verdict"] = "EVIDENCE_WRITE_FAILED"

    return bundle


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    result = execute_session_smoke(
        taskdir=args.taskdir,
        live=args.live,
        confirm_connected=args.confirm_connected,
        confirm_wiring=args.confirm_wiring,
        confirm_voltage=args.confirm_voltage,
        confirm_signal_configured=args.confirm_signal_configured,
        source_declaration=args.source_declaration,
        cli_path=args.cli_path,
        timeout_s=args.timeout,
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))
    verdict = result.get("verdict", result.get("status"))
    if verdict in ("CAPTURE_VALIDITY_PASS", "DRY_RUN"):
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
