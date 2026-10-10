import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

# Ensure scripts directory is importable
REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import dl16_session_smoke as smoke
from dl16_mcp.session import NativeSession


MOCK_WORKER_CODE = r'''
import json, sys, os

commands_seen = []
meta_created = False

for line in sys.stdin:
    try:
        req = json.loads(line)
    except Exception:
        continue
    cmd = req.get("command")
    req_id = req.get("request_id")
    mode = os.environ.get("MOCK_WORKER_MODE", "ok")

    if cmd == "hello":
        print(json.dumps({"request_id": req_id, "ok": True, "protocol": 1}), flush=True)
    elif cmd == "close":
        print(json.dumps({"request_id": req_id, "ok": True, "session": "closing"}), flush=True)
        sys.exit(0)
    elif cmd == "capture":
        commands_seen.append(cmd)
        call_num = len(commands_seen)

        if mode == "fail_first" and call_num == 1:
            print(json.dumps({"request_id": req_id, "ok": False, "error_code": "CAPTURE_FAILED", "message": "Simulated first capture error"}), flush=True)
            continue
        elif mode == "fail_second" and call_num == 2:
            print(json.dumps({"request_id": req_id, "ok": False, "error_code": "CAPTURE_FAILED", "message": "Simulated second capture error"}), flush=True)
            continue
        elif mode == "wrong_channels":
            out_dir = req.get("output_dir", ".")
            cap_id = f"cap-{call_num}"
            cap_folder = os.path.join(out_dir, cap_id)
            os.makedirs(cap_folder, exist_ok=True)
            meta = {
                "sample_rate": 20000000,
                "duration_ms": 10,
                "channels": [0, 1, 8, 14], # Bugged channels
                "sample_counts": {"0": 200000, "1": 200000, "8": 200000, "14": 200000},
                "data_integrity": "COMPLETE",
                "capture_complete_received": True,
                "trigger_ack_received": True,
            }
            with open(os.path.join(cap_folder, "meta.json"), "w", encoding="utf-8") as f:
                json.dump(meta, f)
            res = {
                "success": True,
                "capture_id": cap_id,
                "artifact_dir": cap_folder,
                "data_integrity": "COMPLETE",
                "capture_complete_received": True,
                "trigger_ack_received": True,
                "actual_samples_per_channel": {"0": 200000, "1": 200000, "8": 200000, "14": 200000},
            }
            print(json.dumps({"request_id": req_id, "ok": True, "result": res}), flush=True)
            continue
        elif mode == "wrong_counts":
            out_dir = req.get("output_dir", ".")
            cap_id = f"cap-{call_num}"
            cap_folder = os.path.join(out_dir, cap_id)
            os.makedirs(cap_folder, exist_ok=True)
            meta = {
                "sample_rate": 20000000,
                "duration_ms": 10,
                "channels": [8, 14],
                "sample_counts": {"8": 0, "14": 0},  # 0 samples!
                "data_integrity": "COMPLETE",
                "capture_complete_received": True,
                "trigger_ack_received": True,
            }
            with open(os.path.join(cap_folder, "meta.json"), "w", encoding="utf-8") as f:
                json.dump(meta, f)
            res = {
                "success": True,
                "capture_id": cap_id,
                "artifact_dir": cap_folder,
                "data_integrity": "COMPLETE",
                "capture_complete_received": True,
                "trigger_ack_received": True,
                "actual_samples_per_channel": {"8": 0, "14": 0},
            }
            print(json.dumps({"request_id": req_id, "ok": True, "result": res}), flush=True)
            continue
        elif mode == "all16_counts":
            out_dir = req.get("output_dir", ".")
            cap_id = f"cap-{call_num}"
            cap_folder = os.path.join(out_dir, cap_id)
            os.makedirs(cap_folder, exist_ok=True)
            # Real hardware transmissions populate sample_counts for all 16 channels
            all16 = {str(i): 200000 for i in range(16)}
            meta = {
                "sample_rate": 20000000,
                "duration_ms": 10,
                "channels": [8, 14],
                "sample_counts": all16,
                "data_integrity": "COMPLETE",
                "capture_complete_received": True,
                "trigger_ack_received": True,
            }
            with open(os.path.join(cap_folder, "meta.json"), "w", encoding="utf-8") as f:
                json.dump(meta, f)
            res = {
                "success": True,
                "capture_id": cap_id,
                "artifact_dir": cap_folder,
                "data_integrity": "COMPLETE",
                "capture_complete_received": True,
                "trigger_ack_received": True,
                "actual_samples_per_channel": {"8": 200000, "14": 200000},
            }
            print(json.dumps({"request_id": req_id, "ok": True, "result": res}), flush=True)
            continue

        # Normal ok
        out_dir = req.get("output_dir", ".")
        cap_id = f"cap-{call_num}"
        cap_folder = os.path.join(out_dir, cap_id)
        os.makedirs(cap_folder, exist_ok=True)
        meta = {
            "sample_rate": 20000000,
            "duration_ms": 10,
            "channels": [8, 14],
            "sample_counts": {"8": 200000, "14": 200000},
            "data_integrity": "COMPLETE",
            "capture_complete_received": True,
            "trigger_ack_received": True,
        }
        with open(os.path.join(cap_folder, "meta.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f)
        res = {
            "success": True,
            "capture_id": cap_id,
            "artifact_dir": cap_folder,
            "data_integrity": "COMPLETE",
            "capture_complete_received": True,
            "trigger_ack_received": True,
            "actual_samples_per_channel": {"8": 200000, "14": 200000},
        }
        print(json.dumps({"request_id": req_id, "ok": True, "result": res}), flush=True)
'''


def make_mock_session_factory(worker_mode: str = "ok"):
    def factory(executable: Path) -> NativeSession:
        def popen_factory(_argv, **kwargs):
            env = dict(kwargs.get("env") or os.environ)
            env["MOCK_WORKER_MODE"] = worker_mode
            kwargs["env"] = env
            return subprocess.Popen([sys.executable, "-u", "-c", MOCK_WORKER_CODE], **kwargs)

        return NativeSession(executable, popen_factory=popen_factory)

    return factory


def test_dry_run_does_not_launch_and_outputs_plan(tmp_path):
    taskdir = tmp_path / "smoke_task"
    res = smoke.execute_session_smoke(
        taskdir=taskdir,
        live=False,
        confirm_connected=False,
        confirm_wiring=False,
        confirm_voltage=False,
        confirm_signal_configured=False,
    )
    assert res["status"] == "DRY_RUN"
    assert res["plan"]["live"] is False
    assert res["plan"]["channels"] == [8, 14]
    assert res["plan"]["expected_samples_per_channel"] == 200000
    # Task directory was not created because dry-run avoids side-effects
    assert not taskdir.exists()


def test_live_without_confirmations_is_refused(tmp_path):
    taskdir = tmp_path / "smoke_task"
    res = smoke.execute_session_smoke(
        taskdir=taskdir,
        live=True,
        confirm_connected=False,
        confirm_wiring=True,
        confirm_voltage=True,
        confirm_signal_configured=True,
        source_declaration="valid declaration",
    )
    assert res["status"] == "REFUSED_MISSING_CONFIRMATION"
    assert "confirm_connected" in res["missing_confirmations"]
    assert not taskdir.exists()


def test_live_without_source_declaration_is_refused(tmp_path):
    taskdir = tmp_path / "smoke_task"
    res = smoke.execute_session_smoke(
        taskdir=taskdir,
        live=True,
        confirm_connected=True,
        confirm_wiring=True,
        confirm_voltage=True,
        confirm_signal_configured=True,
        source_declaration="",  # empty
    )
    assert res["status"] == "REFUSED_MISSING_CONFIRMATION"
    assert any("source_declaration" in c for c in res["missing_confirmations"])
    assert not taskdir.exists()


def test_two_successful_exact_channels_and_counts_with_real_all16_schema(tmp_path):
    fake_cli = tmp_path / "atk-dl16.exe"
    fake_cli.write_bytes(b"binary-mock-data")

    taskdir = tmp_path / "smoke_task"
    factory = make_mock_session_factory(worker_mode="all16_counts")

    decl = "on-site wiring safe, signal state unverified; no PWM configured in this block"
    res = smoke.execute_session_smoke(
        taskdir=taskdir,
        live=True,
        confirm_connected=True,
        confirm_wiring=True,
        confirm_voltage=True,
        confirm_signal_configured=True,
        source_declaration=decl,
        cli_path=fake_cli,
        session_factory=factory,
    )

    assert res["verdict"] == "CAPTURE_VALIDITY_PASS"
    assert res["source_declaration"]["declared_text"] == decl
    assert res["source_declaration"]["authority"] == "caller_declared_unverified"
    assert res["source_declaration"]["physical_proof"] is False
    assert len(res["steps"]) == 2
    for step in res["steps"]:
        assert step["status"] == "STEP_SUCCESS"
        assert step["validity"]["valid"] is True
        assert step["validity"]["exact_channels"] == [8, 14]

    assert res["cleanup"]["session_closed"] is True
    # Verify step_1.json, step_2.json, and bundle are persisted with fsync
    run_dir = Path(res["run_dir"])
    assert (run_dir / "step_1.json").is_file()
    assert (run_dir / "step_2.json").is_file()
    assert (run_dir / "smoke_bundle.json").is_file()
    step_1_data = json.loads((run_dir / "step_1.json").read_text(encoding="utf-8"))
    assert step_1_data["status"] == "STEP_SUCCESS"

    assert res["cleanup"]["session_closed"] is True
    # Verify bundle and journal files are written to unique dir
    run_dir = Path(res["run_dir"])
    assert (run_dir / "smoke_bundle.json").is_file()
    journal_dir = run_dir / "journal"
    assert len(list(journal_dir.glob("*.jsonl"))) == 1


def test_first_error_stops_before_second(tmp_path):
    fake_cli = tmp_path / "atk-dl16.exe"
    fake_cli.write_bytes(b"binary-mock-data")

    taskdir = tmp_path / "smoke_task"
    factory = make_mock_session_factory(worker_mode="fail_first")

    res = smoke.execute_session_smoke(
        taskdir=taskdir,
        live=True,
        confirm_connected=True,
        confirm_wiring=True,
        confirm_voltage=True,
        confirm_signal_configured=True,
        source_declaration="valid declaration",
        cli_path=fake_cli,
        session_factory=factory,
    )

    assert res["verdict"] == "FIRST_REQUEST_FAILED"
    assert len(res["steps"]) == 1
    assert res["steps"][0]["status"] == "SESSION_FAILURE"
    assert res["steps"][0]["error_code"] == "CAPTURE_FAILED"
    assert res["steps"][0]["message"] == "Simulated first capture error"
    assert res["cleanup"]["session_closed"] is True
    # Verify second step file was not written
    run_dir = Path(res["run_dir"])
    assert (run_dir / "step_1.json").is_file()
    assert not (run_dir / "step_2.json").exists()


def test_wrong_metadata_channels_fails_criteria(tmp_path):
    fake_cli = tmp_path / "atk-dl16.exe"
    fake_cli.write_bytes(b"binary-mock-data")

    taskdir = tmp_path / "smoke_task"
    factory = make_mock_session_factory(worker_mode="wrong_channels")

    res = smoke.execute_session_smoke(
        taskdir=taskdir,
        live=True,
        confirm_connected=True,
        confirm_wiring=True,
        confirm_voltage=True,
        confirm_signal_configured=True,
        source_declaration="decl",
        cli_path=fake_cli,
        session_factory=factory,
    )

    assert res["verdict"] == "FIRST_REQUEST_FAILED"
    assert len(res["steps"]) == 1
    assert res["steps"][0]["status"] == "CAPTURE_CRITERIA_MISMATCH"
    assert any("channels" in r for r in res["steps"][0]["reasons"])
    assert res["cleanup"]["session_closed"] is True


def test_wrong_sample_counts_fails_criteria(tmp_path):
    fake_cli = tmp_path / "atk-dl16.exe"
    fake_cli.write_bytes(b"binary-mock-data")

    taskdir = tmp_path / "smoke_task"
    factory = make_mock_session_factory(worker_mode="wrong_counts")

    res = smoke.execute_session_smoke(
        taskdir=taskdir,
        live=True,
        confirm_connected=True,
        confirm_wiring=True,
        confirm_voltage=True,
        confirm_signal_configured=True,
        source_declaration="decl",
        cli_path=fake_cli,
        session_factory=factory,
    )

    assert res["verdict"] == "FIRST_REQUEST_FAILED"
    assert len(res["steps"]) == 1
    assert res["steps"][0]["status"] == "CAPTURE_CRITERIA_MISMATCH"
    assert any("samples 0" in r for r in res["steps"][0]["reasons"])
    assert res["cleanup"]["session_closed"] is True


def test_counts_key_non_integer_fails_closed_without_crash():
    res = {
        "success": True,
        "data_integrity": "COMPLETE",
        "capture_complete_received": True,
        "trigger_ack_received": True,
        "actual_samples_per_channel": {"bad_channel_key": 200000},
    }
    meta = {
        "sample_rate": 20000000,
        "duration_ms": 10,
        "channels": [8, 14],
        "sample_counts": {"8": 200000, "14": 200000},
        "data_integrity": "COMPLETE",
        "capture_complete_received": True,
        "trigger_ack_received": True,
    }
    v = smoke.inspect_capture_validity(res, meta)
    assert v["valid"] is False
    assert any("non-integer" in r for r in v["reasons"])


def test_write_failure_stops_next_request_and_fails_closed(tmp_path, monkeypatch):
    fake_cli = tmp_path / "atk-dl16.exe"
    fake_cli.write_bytes(b"binary-mock-data")

    taskdir = tmp_path / "smoke_task"
    factory = make_mock_session_factory(worker_mode="ok")

    # Simulate disk write failure on pre-dispatch of step 2
    orig_durable_write = smoke.durable_write_json

    def failing_write(path, data):
        if "step_2.json" in str(path):
            raise OSError("Disk I/O error simulated on step 2")
        orig_durable_write(path, data)

    monkeypatch.setattr(smoke, "durable_write_json", failing_write)

    res = smoke.execute_session_smoke(
        taskdir=taskdir,
        live=True,
        confirm_connected=True,
        confirm_wiring=True,
        confirm_voltage=True,
        confirm_signal_configured=True,
        source_declaration="decl",
        cli_path=fake_cli,
        session_factory=factory,
    )

    assert res["verdict"] == "EVIDENCE_WRITE_FAILED"
    assert len(res["steps"]) == 2
    assert res["steps"][1]["status"] == "PRE_DISPATCH_WRITE_FAILED"
    assert res["cleanup"]["session_closed"] is True


def test_cleanup_failure_overrides_pass(tmp_path):
    fake_cli = tmp_path / "atk-dl16.exe"
    fake_cli.write_bytes(b"binary-mock-data")

    taskdir = tmp_path / "smoke_task"

    def bad_cleanup_factory(executable: Path) -> NativeSession:
        session = make_mock_session_factory(worker_mode="ok")(executable)

        def failing_close():
            raise RuntimeError("close failure simulated")

        session.close = failing_close
        return session

    res = smoke.execute_session_smoke(
        taskdir=taskdir,
        live=True,
        confirm_connected=True,
        confirm_wiring=True,
        confirm_voltage=True,
        confirm_signal_configured=True,
        source_declaration="decl",
        cli_path=fake_cli,
        session_factory=bad_cleanup_factory,
    )

    assert res["verdict"] == "CLEANUP_FAILED"
    assert res["cleanup"]["session_closed"] is False
    assert "close failure simulated" in res["cleanup"]["clean_error"]


def test_constructor_exception_is_recorded_in_bundle(tmp_path):
    fake_cli = tmp_path / "atk-dl16.exe"
    fake_cli.write_bytes(b"binary-mock-data")

    taskdir = tmp_path / "smoke_task"

    def broken_constructor(_exe: Path) -> NativeSession:
        raise OSError("failed to spawn native worker")

    res = smoke.execute_session_smoke(
        taskdir=taskdir,
        live=True,
        confirm_connected=True,
        confirm_wiring=True,
        confirm_voltage=True,
        confirm_signal_configured=True,
        source_declaration="decl",
        cli_path=fake_cli,
        session_factory=broken_constructor,
    )

    assert res["verdict"] == "SESSION_INIT_FAILED"
    assert "failed to spawn native worker" in res["constructor_error"]
    assert res["cleanup"]["session_closed"] is True
    run_dir = Path(res["run_dir"])
    assert (run_dir / "smoke_bundle.json").is_file()


def test_cleanup_always_executed_and_environment_restored(tmp_path):
    fake_cli = tmp_path / "atk-dl16.exe"
    fake_cli.write_bytes(b"binary-mock-data")

    taskdir = tmp_path / "smoke_task"
    factory = make_mock_session_factory(worker_mode="ok")

    orig_env = os.environ.get("DL16_SESSION_JOURNAL_DIR")
    try:
        os.environ["DL16_SESSION_JOURNAL_DIR"] = "custom_original_journal"
        res = smoke.execute_session_smoke(
            taskdir=taskdir,
            live=True,
            confirm_connected=True,
            confirm_wiring=True,
            confirm_voltage=True,
            confirm_signal_configured=True,
            source_declaration="valid declaration",
            cli_path=fake_cli,
            session_factory=factory,
        )
        assert res["cleanup"]["session_closed"] is True
        assert os.environ.get("DL16_SESSION_JOURNAL_DIR") == "custom_original_journal"
    finally:
        if orig_env is None:
            os.environ.pop("DL16_SESSION_JOURNAL_DIR", None)
        else:
            os.environ["DL16_SESSION_JOURNAL_DIR"] = orig_env


@pytest.mark.parametrize("mode,expected", [("ok", 20), ("fail_second", 2)])
def test_bounded_repeatability_and_stop_on_error(tmp_path, mode, expected):
    res = smoke.execute_session_smoke(
        taskdir=tmp_path, live=True, confirm_connected=True,
        confirm_wiring=True, confirm_voltage=True, confirm_signal_configured=True,
        source_declaration="synthetic mock", cli_path=Path(sys.executable),
        session_factory=make_mock_session_factory(mode), requests=20,
    )
    assert len(res["steps"]) == expected
    assert res["verdict"] == ("CAPTURE_VALIDITY_PASS" if mode == "ok" else "SECOND_REQUEST_FAILED")


@pytest.mark.parametrize("count", [0, 1, 21, True, 2.5])
def test_invalid_block_size_rejected_without_launch(tmp_path, count):
    with pytest.raises(ValueError, match="requests"):
        smoke.execute_session_smoke(tmp_path, False, False, False, False, False, requests=count)
