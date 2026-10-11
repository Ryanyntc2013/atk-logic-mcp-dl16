"""TASK055 actual production receive/writer/dispatcher; transport is SYNTHETIC_OFFLINE."""
import json
import subprocess
import time
from pathlib import Path

import pytest

from dl16_mcp import backend, service

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tests/native/build/Release/dl16-experimental-stream-test.exe"
CONFIRM = "CONFIRMED_SAFE_WIRING_GUI_CLOSED"


@pytest.mark.skipif(not HARNESS.exists(), reason="native Stream integration harness not built")
def test_actual_receive_incremental_all16_cancel_and_eof(tmp_path):
    directory = tmp_path / "stream"
    proc = subprocess.Popen([str(HARNESS), str(directory)], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, text=True)

    def request(command, **fields):
        proc.stdin.write(json.dumps({"request_id": command, "command": command, **fields}) + "\n")
        proc.stdin.flush()
        return json.loads(proc.stdout.readline())

    config = {"channels": [8, 14], "sample_rate_hz": 1_000_000, "duration_ms": 1000,
              "threshold_voltage": 1.6, "output_dir": str(directory), "experimental_opt_in": True,
              "safety_confirmation": CONFIRM}
    try:
        assert request("stream_start", **config)["state"] == "running"
        deadline = time.monotonic() + 3
        previous = 0
        while True:
            poll = request("stream_poll", operation_id="stream_start")
            assert poll["state"] == "running"
            progress = poll["progress"]
            assert progress["stored_bytes"] >= previous
            previous = progress["stored_bytes"]
            assert set(progress) == {"stored_bytes", "reads", "receive_elapsed_ns",
                                     "packed_write_elapsed_ns", "packed_flush_elapsed_ns"}
            if previous >= 64:
                assert progress["reads"] >= 16
                assert sum((directory / f"ch{ch}.packed.bin").stat().st_size
                           for ch in range(16)) >= previous
                break
            assert time.monotonic() < deadline
            time.sleep(0.005)
        assert request("capture_start", channels=[8], sample_rate_hz=1_000_000,
                       duration_ms=10)["error_code"] == "SESSION_BUSY"
        assert request("stream_cancel", operation_id="wrong")["error_code"] == "UNKNOWN_OPERATION"
        assert request("stream_cancel", operation_id="stream_start")["ok"]
        while True:
            reply = request("stream_poll", operation_id="stream_start")
            if reply["state"] == "finished":
                break
            assert time.monotonic() < deadline
        result = reply["response"]["result"]
        assert result["reason"] == "CANCELLED"
        assert 64 <= result["stored_bytes"] <= 2048
        assert reply["progress"]["stored_bytes"] == result["stored_bytes"]
        assert result["receive_elapsed_ns"] > 0
        assert result["packed_write_elapsed_ns"] > 0
        assert result["packed_flush_elapsed_ns"] > 0
        assert result["cleanup_stop_ok"]
        assert result["analysis_ready"] is False
        assert result["success"] is False
        meta = json.loads((directory / "stream_meta.json").read_text())
        assert meta["evidence_source"] == "SYNTHETIC_OFFLINE"
        assert meta["tail_status"] == "UNKNOWN"
        assert meta["data_integrity"] == "INCOMPLETE"
        assert len(meta["channels"]) == 16
        for ch in range(16):
            data = (directory / f"ch{ch}.packed.bin").read_bytes()
            assert data and data == b"\x81\xaa\xaa\xaa" * (len(data) // 4)
        assert request("close")["ok"]
        assert proc.wait(timeout=3) == 0
    finally:
        if proc.poll() is None:
            proc.stdin.close()
            proc.wait(timeout=3)
        proc.stdout.close()
        if not proc.stdin.closed:
            proc.stdin.close()
    eof = tmp_path / "eof"
    config["output_dir"] = str(eof)
    line = json.dumps({"request_id": "eof", "command": "stream_start", **config})
    completed = subprocess.run([str(HARNESS), str(eof)], input=line + "\n", capture_output=True,
                               text=True, timeout=3, check=True)
    assert json.loads(completed.stdout.splitlines()[0])["ok"]
    assert json.loads((eof / "stream_meta.json").read_text())["reason"] == "CANCELLED"
    assert sum(p.stat().st_size for p in eof.glob("*.packed.bin")) <= 2048


def test_host_prelaunch_confirmation_and_all16_budget(monkeypatch):
    monkeypatch.setattr(backend, "find_native_cli", lambda: pytest.fail("must reject before worker"))
    assert service.logic_stream_start()["error_code"] == "EXPERIMENTAL_OPT_IN_REQUIRED"
    assert service.logic_stream_start(True)["error_code"] == "INVALID_STREAM"
    assert service.logic_stream_start(True, CONFIRM, [8, 14], 20_000_000, 30_000)["error_code"] == "INVALID_STREAM"
    assert service.logic_stream_start(True, CONFIRM, [8, 14], 25_000_000, 10)["error_code"] == "INVALID_STREAM"


def test_public_start_and_control_route_without_relabel(monkeypatch, tmp_path):
    class Owner:
        failed = False
        def request(self, payload, **kwargs):
            if payload["command"] == "stream_start":
                assert payload["experimental_opt_in"] is True
                assert payload["safety_confirmation"] == CONFIRM
                assert payload["channels"] == [8, 14]
                return {"ok": True, "operation_id": "op", "state": "running"}
            return {"ok": True, "state": "finished", "progress": {"stored_bytes": 17, "reads": 2}, "response": {"result": {
                "success": False, "data_integrity": "INCOMPLETE", "tail_status": "UNKNOWN"}}}
    owner = Owner()
    monkeypatch.setattr(backend, "_session_enabled", lambda: True)
    monkeypatch.setattr(backend, "find_native_cli", lambda: Path("worker"))
    monkeypatch.setattr(backend, "_get_session", lambda _: owner)
    monkeypatch.setattr(backend, "captures_dir", lambda: tmp_path)
    monkeypatch.setattr(backend, "_SESSION", owner)
    assert service.logic_stream_start(True, CONFIRM, [8, 14])["operation_id"] == "op"
    assert service.logic_stream_poll("op")["progress"] == {"stored_bytes": 17, "reads": 2}
    assert not service.logic_stream_poll("op")["response"]["result"]["success"]
    assert service.logic_stream_cancel("op")["response"]["result"]["tail_status"] == "UNKNOWN"


@pytest.mark.skipif(not HARNESS.exists(), reason="native Stream integration harness not built")
@pytest.mark.parametrize("mode,reason", [("usb_error", "USB_ERROR"), ("short", "SHORT_RX"),
                                       ("send_error", "OWNER_ERROR"), ("order6", "ORDER6_OBSERVED"),
                                       ("normal", "DEADLINE"), ("stop_error", "DEADLINE"),
                                       ("metadata_error", None), ("write_error", None)])
def test_actual_stream_terminal_failures_and_progress_reset(tmp_path, mode, reason):
    directory = tmp_path / mode
    if mode == "write_error":
        directory.mkdir()
    proc = subprocess.Popen([str(HARNESS), str(directory), mode], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, text=True)

    def request(command, **fields):
        proc.stdin.write(json.dumps({"request_id": command, "command": command, **fields}) + "\n")
        proc.stdin.flush()
        return json.loads(proc.stdout.readline())

    config = {"channels": [8, 14], "sample_rate_hz": 1_000_000, "duration_ms": 100,
              "threshold_voltage": 1.6, "output_dir": str(directory), "experimental_opt_in": True,
              "safety_confirmation": CONFIRM}
    try:
        for iteration in range(2):
            assert request("stream_start", **config)["state"] == "running"
            deadline = time.monotonic() + 3
            while True:
                reply = request("stream_poll", operation_id="stream_start")
                if reply["state"] == "finished":
                    break
                assert time.monotonic() < deadline
                time.sleep(0.005)
            if reason is None or iteration == 1:
                assert reply["response"]["error_code"] == "STREAM_WRITE_ERROR"
                if mode == "metadata_error" and iteration == 0:
                    assert reply["progress"]["stored_bytes"] == 8
                    assert reply["progress"]["reads"] == 2
                    assert sum(p.stat().st_size for p in directory.glob("*.packed.bin")) == 8
                else:
                    assert reply["progress"]["stored_bytes"] == 0
                    assert reply["progress"]["reads"] == 0
            else:
                result = reply["response"]["result"]
                assert result["reason"] == reason
                assert result["cleanup_stop_ok"] is (mode != "stop_error")
                assert result["success"] is False
                assert result["valid_sample_count"] is None
                assert reply["progress"]["stored_bytes"] == result["stored_bytes"]
                assert result["stored_bytes"] <= 2048
        assert request("close")["ok"]
        assert proc.wait(timeout=3) == 0
    finally:
        if proc.poll() is None:
            proc.stdin.close()
            proc.wait(timeout=3)
        proc.stdout.close()
        if not proc.stdin.closed:
            proc.stdin.close()
