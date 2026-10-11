"""DL16-TASK-066 hardware acceptance harness. DEFAULT: OFFLINE PLAN ONLY.

This module must never open USB without --execute, all operator confirmations,
and an interactive acknowledgement. It runs only one bounded case per process.
No firmware, USB reset, endpoint clear, driver change or arbitrary commands.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

CASES = {
    "normal": "Real Buffer+Stream loopback diagnostic; verify PWM off after exit",
    "pwm1-reject": "Configure actual PWM0; inject rejection before PWM1 configure; verify cleanup",
    "buffer-reject": "Configure actual PWM0/PWM1; inject Buffer failure before capture; verify cleanup",
    "stream-poll-error": "Run real Stream after real Buffer; inject one poll failure; verify cancel/cleanup",
}
FLAGS = (
    "confirm_connected", "confirm_loopback", "confirm_voltage",
    "confirm_gui_closed", "confirm_exclusive_owner", "confirm_scope",
)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--case", choices=CASES, default="normal")
    p.add_argument("--execute", action="store_true",
                   help="Explicitly enable real physical device operation; default is OFFLINE")
    for flag in FLAGS:
        p.add_argument("--" + flag.replace("_", "-"), action="store_true")
    p.add_argument("--evidence-root", type=Path, default=Path("artifacts/hil/DL16-TASK-066"))
    return p


def missing_confirmations(args: argparse.Namespace) -> list[str]:
    return [name for name in FLAGS if getattr(args, name) is not True]


def _record(path: Path, payload: dict) -> None:
    # Only our own, unique task run directory is used; do not overwrite evidence.
    with path.open("x", encoding="utf-8") as fp:
        json.dump(payload, fp, indent=2, ensure_ascii=False, default=str)
        fp.write("\n")
        fp.flush()
        os.fsync(fp.fileno())


def _hash_manifest(directory: Path) -> None:
    manifest = directory / "SHA256SUMS.txt"
    with manifest.open("x", encoding="ascii") as out:
        for file in sorted(directory.rglob("*")):
            if not file.is_file() or file == manifest:
                continue
            relative = file.relative_to(directory).as_posix()
            digest = hashlib.sha256(file.read_bytes()).hexdigest()
            out.write(f"{digest}  {relative}\n")


def _git_rev() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                              text=True, timeout=3, check=True).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "UNKNOWN"


@contextmanager
def fault_injection(service, name: str, events: list[str]):
    """Patch only an application-layer return path; never fabricate physical stop."""
    original_pwm = service.logic_pwm
    original_buffer = service.logic_capture
    original_poll = service.logic_stream_poll
    seen = {"poll": 0, "pwm1": 0}

    def pwm(output, action="configure", *a, **kwargs):
        if name == "pwm1-reject" and action == "configure" and output == 1 and seen["pwm1"] == 0:
            seen["pwm1"] += 1
            events.append("INJECTED_PWM1_CONFIG_REJECTION_WITHOUT_DEVICE_WRITE")
            return {"success": False, "error_code": "TASK066_INJECTED_PWM1_REJECT"}
        return original_pwm(output, action, *a, **kwargs)

    def buffer(*a, **kwargs):
        if name == "buffer-reject":
            events.append("INJECTED_BUFFER_REJECTION_WITHOUT_DEVICE_CAPTURE")
            return {"success": False, "error_code": "TASK066_INJECTED_BUFFER_REJECT"}
        return original_buffer(*a, **kwargs)

    def poll(operation_id):
        if name == "stream-poll-error" and seen["poll"] == 0:
            seen["poll"] += 1
            events.append("INJECTED_ONE_STREAM_POLL_ERROR_AFTER_REAL_START")
            return {"success": False, "error_code": "TASK066_INJECTED_POLL_ERROR"}
        return original_poll(operation_id)

    try:
        service.logic_pwm = pwm
        service.logic_capture = buffer
        service.logic_stream_poll = poll
        yield
    finally:
        service.logic_pwm = original_pwm
        service.logic_capture = original_buffer
        service.logic_stream_poll = original_poll


def _postflight(service, backend) -> dict:
    """Status only after successful software cleanup; no implicit reset/retry."""
    if backend.has_owned_session():
        return {"success": False, "error_code": "OWNER_STILL_PRESENT"}
    try:
        status = service.logic_status()
        close = service.logic_session_close()
        return {"success": bool(status.get("connected") and status.get("ready") and close.get("success")),
                "status": status, "postflight_close": close}
    except Exception as exc:
        return {"success": False, "error_code": "POSTFLIGHT_EXCEPTION", "message": str(exc)}


def execute_hil(args: argparse.Namespace) -> int:
    missing = missing_confirmations(args)
    if missing:
        print(json.dumps({"status": "REFUSED", "reason": "Missing operator confirmations",
                          "missing": missing}, indent=2))
        return 2
    if not sys.stdin.isatty():
        print("REFUSED: live HIL requires a human operator on an interactive terminal.", file=sys.stderr)
        return 2

    print("This will send REAL commands to DL16. One case only:", args.case)
    print("Required: PWM0->CH8, PWM1->CH14, common ground, safe <=3.3 V levels.")
    print("GUI closed, one USB owner, oscilloscope/independent probe connected to both PWM outputs.")
    print("If PWM remains active after a failure, stop testing and use approved physical shutdown.")
    if input("Type RUN-DL16-066 to begin: ").strip() != "RUN-DL16-066":
        print("REFUSED: explicit on-site acknowledgement was not given.")
        return 2

    # Import after operator confirmation. Python import must not open USB.
    from dl16_mcp import service, backend

    if os.environ.get("DL16_BACKEND_MODE", "oneshot").lower() != "session":
        print("REFUSED: set DL16_BACKEND_MODE=session explicitly.", file=sys.stderr)
        return 2
    if backend.find_native_cli() is None:
        print("REFUSED: pinned patched native CLI not found.", file=sys.stderr)
        return 2
    if backend.has_owned_session():
        print("REFUSED: another operation owns this Python MCP session.", file=sys.stderr)
        return 2

    run_name = (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                + "-" + args.case + "-" + uuid.uuid4().hex[:8])
    folder = args.evidence_root.expanduser().resolve() / run_name
    folder.mkdir(parents=True, exist_ok=False)
    os.environ["DL16_DATA_DIR"] = str(folder / "data")
    events: list[str] = []
    details = {
        "task": "DL16-TASK-066", "case": args.case,
        "case_description": CASES[args.case],
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_sha": _git_rev(), "native_cli": str(backend.find_native_cli()),
        "native_cli_sha256": hashlib.sha256(backend.find_native_cli().read_bytes()).hexdigest(),
        "operator_confirmations": {n: True for n in FLAGS},
        "note": "Operator asserted safety; software cannot independently verify wiring/voltage.",
    }
    _record(folder / "preflight.json", details)

    result = {}
    postflight = {"success": False, "reason": "not attempted"}
    try:
        with fault_injection(service, args.case, events):
            result = service.logic_self_test(confirm_safe_wiring=True)
        # Only attempt fresh session after the self-test confirms its own cleanup.
        if result.get("cleanup_ok") is True:
            postflight = _postflight(service, backend)
        else:
            postflight = {"success": False, "reason": "self-test cleanup not confirmed; no new USB owner opened"}
    except Exception as exc:
        result = {"success": False, "error_code": "HARNESS_EXCEPTION", "message": str(exc)}
    finally:
        # Never hide failures; best-effort close existing owned worker, no USB resets.
        if backend.has_owned_session():
            try:
                events.append("FINAL_BEST_EFFORT_CLOSE")
                result["harness_final_close"] = service.logic_session_close()
            except Exception as exc:
                result["harness_final_close"] = {"success": False, "message": str(exc)}

        _record(folder / "result.json", {
            "self_test": result, "postflight": postflight, "injection_events": events,
        })

    print("Hardware activity ended. Do NOT infer physical off from native command ACK.")
    print("Independently inspect oscilloscope on BOTH PWM outputs and record the evidence.")
    try:
        observed = input("PWM0 and PWM1 are physically OFF? [off/on/unknown]: ").strip().lower()
    except EOFError:
        observed = "unknown"
    if observed not in ("off", "on", "unknown"):
        observed = "unknown"
    try:
        evidence = input("Independent scope evidence path or note (not auto-verified): ").strip()
    except EOFError:
        evidence = ""
    physical_off = observed == "off" and bool(evidence)
    expected_success = args.case == "normal"
    outcome_matches = bool(result.get("success")) == expected_success
    cleanup_pass = result.get("cleanup_ok") is True
    postflight_pass = postflight.get("success") is True
    # In injected error cases, the error should be specifically observed.
    expected_codes = {
        "pwm1-reject": "PWM_CONFIG_FAILED",
        "buffer-reject": "BUFFER_CAPTURE_FAILED",
        "stream-poll-error": "STREAM_POLL_FAILED",
    }
    injection_match = (args.case == "normal" or
                       result.get("error_code") == expected_codes.get(args.case))
    verdict = ("PASS_UNCALIBRATED" if physical_off and cleanup_pass
               and postflight_pass and outcome_matches and injection_match else "FAIL_OR_UNVERIFIED")
    _record(folder / "operator_observation.json", {
        "physical_pwm_off_claimed_by_operator": observed,
        "independent_observation_note": evidence,
        "physical_off_evidence_supplied": physical_off,
        "software_cleanup_ok": cleanup_pass,
        "fresh_postflight_ready": postflight_pass,
        "expected_outcome_observed": outcome_matches and injection_match,
        "verdict": verdict,
        "absolute_timing_calibrated": False,
        "scope_observation_requires_independent_review": True,
    })
    _hash_manifest(folder)
    print(json.dumps({"task": "DL16-TASK-066", "case": args.case,
                      "verdict": verdict, "evidence_dir": str(folder)}, indent=2))
    return 0 if verdict == "PASS_UNCALIBRATED" else 1


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if not args.execute:
        print(json.dumps({
            "status": "HIL_NOT_RUN", "mode": "OFFLINE_PLAN_ONLY",
            "case": args.case, "purpose": CASES[args.case],
            "available_cases": CASES,
            "live_required_confirmations": ["--" + n.replace("_", "-") for n in FLAGS],
            "live_requires": ["--execute", "interactive acknowledgement",
                              "DL16_BACKEND_MODE=session", "patched native CLI",
                              "scope observation on both PWM outputs"],
        }, indent=2, ensure_ascii=False))
        return 0
    return execute_hil(args)


if __name__ == "__main__":
    raise SystemExit(main())
