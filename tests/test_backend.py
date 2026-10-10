import json
from unittest.mock import patch

from dl16_mcp import backend
from dl16_mcp.config import CaptureRequest


def test_invalid_channel_fails_closed():
    result = backend.capture(CaptureRequest(channels=(0, 18)))
    assert result["success"] is False
    assert result["evidence_source"] == "NONE"


def test_missing_cli_no_hardware_claim(monkeypatch):
    monkeypatch.setenv("DL16_CLI_PATH", "/path/does/not/exist")
    assert backend.status()["connected"] is False
    assert backend.capture(CaptureRequest())["error_code"] == "CLI_MISSING"


def test_fake_success_without_ack_rejected(monkeypatch, tmp_path):
    file = tmp_path / "atk-dl16.exe"
    file.write_text("mock")
    monkeypatch.setenv("DL16_CLI_PATH", str(file))
    class Result:
        returncode = 0
        stdout = json.dumps({"success": True, "data_integrity": "COMPLETE", "capture_complete_received": True,
                             "trigger_ack_received": False})
        stderr = ""
    with patch("dl16_mcp.backend.subprocess.run", return_value=Result()):
        r = backend.capture(CaptureRequest())
    assert r["success"] is False
    assert r["error_code"] == "EVIDENCE_INCOMPLETE"


def _cli_file(monkeypatch, tmp_path):
    file = tmp_path / "atk-dl16.exe"
    file.write_text("mock")
    monkeypatch.setenv("DL16_CLI_PATH", str(file))


def test_capture_retries_once_on_device_info_open_error(monkeypatch, tmp_path):
    _cli_file(monkeypatch, tmp_path)
    fail = json.dumps({"success": False, "error_code": "PROTOCOL_ERROR",
                       "message": "Failed to parse FPGA device info packet"})
    ok = json.dumps({"success": True, "data_integrity": "COMPLETE",
                     "capture_complete_received": True, "trigger_ack_received": True})

    class R:
        def __init__(self, out, rc):
            self.stdout = out
            self.stderr = ""
            self.returncode = rc

    calls = {"n": 0}

    def fake_run(cmd, **kwargs):
        calls["n"] += 1
        return R(ok, 0) if calls["n"] == 2 else R(fail, 1)

    with patch("dl16_mcp.backend.subprocess.run", side_effect=fake_run):
        r = backend.capture(CaptureRequest())
    assert r["success"] is True
    assert calls["n"] == 2


def test_capture_does_not_retry_incomplete_evidence(monkeypatch, tmp_path):
    _cli_file(monkeypatch, tmp_path)
    incomplete = json.dumps({"success": True, "data_integrity": "INCOMPLETE",
                             "capture_complete_received": False, "trigger_ack_received": True})

    class R:
        returncode = 0
        stdout = incomplete
        stderr = ""

    with patch("dl16_mcp.backend.subprocess.run", return_value=R()) as m:
        r = backend.capture(CaptureRequest())
    assert r["success"] is False
    assert r["error_code"] == "EVIDENCE_INCOMPLETE"
    assert m.call_count == 1


def test_status_retries_once_on_device_info_open_error(monkeypatch, tmp_path):
    _cli_file(monkeypatch, tmp_path)

    class R:
        def __init__(self, out, err, rc):
            self.stdout = out
            self.stderr = err
            self.returncode = rc

    calls = {"n": 0}

    def fake_run(cmd, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return R("", "Error opening device: Failed to parse FPGA device info packet", 1)
        return R("Model: DL16 Plus\n", "", 0)

    with patch("dl16_mcp.backend.subprocess.run", side_effect=fake_run):
        s = backend.status()
    assert s["connected"] is True
    assert calls["n"] == 2


def test_capture_passes_trigger_position(monkeypatch, tmp_path):
    _cli_file(monkeypatch, tmp_path)
    captured = {}

    class R:
        returncode = 0
        stdout = json.dumps({"success": True, "data_integrity": "COMPLETE",
                             "capture_complete_received": True, "trigger_ack_received": True})
        stderr = ""

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return R()

    with patch("dl16_mcp.backend.subprocess.run", side_effect=fake_run):
        backend.capture(CaptureRequest(trigger="ch0:rising"), trigger_position_percent=50.0)
    assert "--trigger-position" in captured["cmd"]
    assert "50.0" in captured["cmd"]


def test_capture_rejects_bad_trigger_position(monkeypatch, tmp_path):
    _cli_file(monkeypatch, tmp_path)
    r = backend.capture(CaptureRequest(), trigger_position_percent=150.0)
    assert r["success"] is False
    assert r["error_code"] == "INVALID_CAPTURE_CONFIG"
