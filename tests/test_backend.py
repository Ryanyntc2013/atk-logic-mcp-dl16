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


def test_capture_passes_trigger_timeout(monkeypatch, tmp_path):
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
        backend.capture(CaptureRequest(trigger="ch0:rising"), trigger_timeout_sec=3)
    assert "--trigger-timeout" in captured["cmd"]
    assert "3" in captured["cmd"]


class _Res:
    def __init__(self, rc, stdout="", stderr=""):
        self.returncode = rc
        self.stdout = stdout
        self.stderr = stderr


def test_status_retries_open_failure_and_logs(monkeypatch, tmp_path):
    _cli_file(monkeypatch, tmp_path)
    monkeypatch.setattr(backend, "_sleep", lambda s: None)
    seq = [_Res(1, stderr="failed to parse FPGA device info"),
           _Res(1, stderr="failed to parse FPGA device info"),
           _Res(0, stdout="FPGA: v2.22\n")]
    with patch("dl16_mcp.backend.subprocess.run", side_effect=seq):
        r = backend.status()
    assert r["connected"] is True
    assert r["attempts"] == 3
    assert [e["attempt"] for e in r["retry_log"]] == [1, 2]


def test_status_gives_up_after_max_attempts(monkeypatch, tmp_path):
    _cli_file(monkeypatch, tmp_path)
    monkeypatch.setattr(backend, "_sleep", lambda s: None)
    with patch("dl16_mcp.backend.subprocess.run",
               return_value=_Res(1, stderr="failed to parse FPGA device info")) as run:
        r = backend.status()
    assert run.call_count == backend.MAX_ATTEMPTS
    assert r["connected"] is False
    assert r["attempts"] == backend.MAX_ATTEMPTS
    assert len(r["retry_log"]) == backend.MAX_ATTEMPTS - 1


def test_status_does_not_retry_unrelated_error(monkeypatch, tmp_path):
    _cli_file(monkeypatch, tmp_path)
    with patch("dl16_mcp.backend.subprocess.run", return_value=_Res(1, stderr="no device")) as run:
        r = backend.status()
    assert run.call_count == 1
    assert r["retry_log"] == []


def test_backoff_is_increasing():
    assert backend._backoff_seconds(1) < backend._backoff_seconds(2)


def test_capture_retry_recorded_as_warning(monkeypatch, tmp_path):
    _cli_file(monkeypatch, tmp_path)
    monkeypatch.setattr(backend, "_sleep", lambda s: None)
    bad = json.dumps({"success": False, "error_code": "CLI_CAPTURE_FAILED",
                      "message": "failed to parse FPGA device info"})
    good = json.dumps({"success": True, "data_integrity": "COMPLETE", "capture_complete_received": True,
                       "trigger_ack_received": True, "file": "x.atkdl"})
    with patch("dl16_mcp.backend.subprocess.run", side_effect=[_Res(1, bad), _Res(0, good)]):
        r = backend.capture(CaptureRequest())
    assert r["success"] is True
    assert r["attempts"] == 2
    assert len(r["retry_log"]) == 1
    assert any("open-retry" in w for w in r["warnings"])


def test_capture_timeout_never_retried(monkeypatch, tmp_path):
    _cli_file(monkeypatch, tmp_path)
    import subprocess as sp
    with patch("dl16_mcp.backend.subprocess.run", side_effect=sp.TimeoutExpired("cli", 1)) as run:
        r = backend.capture(CaptureRequest(), timeout_s=1.0)
    assert run.call_count == 1
    assert r["error_code"] == "HOST_TIMEOUT"


def test_session_mode_routes_status_and_capture_without_oneshot(monkeypatch, tmp_path):
    _cli_file(monkeypatch, tmp_path)
    monkeypatch.setenv("DL16_BACKEND_MODE", "session")
    calls = []

    class FakeSession:
        def request(self, request, *, timeout_s):
            calls.append((request, timeout_s))
            if request["command"] == "status":
                return {"request_id": "s1", "ok": True, "session": "ready",
                        "transport_open": True, "device": {"model": "DL16 Plus", "channels": 16}}
            return {"request_id": "s2", "ok": True, "session": "ready",
                    "result": {"success": True, "data_integrity": "COMPLETE",
                               "capture_complete_received": True, "trigger_ack_received": True}}

    fake = FakeSession()
    monkeypatch.setattr(backend, "_get_session", lambda cli: fake)
    with patch("dl16_mcp.backend.subprocess.run", side_effect=AssertionError("one-shot path must not run")):
        status = backend.status()
        capture = backend.capture(CaptureRequest(channels=(0,), trigger="ch0:rising"), trigger_timeout_sec=3)
    assert status["backend"] == "native-session" and status["ready"] is True
    assert capture["backend"] == "native-session" and capture["success"] is True
    request = calls[1][0]
    assert request["trigger_timeout_sec"] == 3
    assert request["channels"] == [0]


def test_session_failure_never_falls_back_or_replays(monkeypatch, tmp_path):
    from dl16_mcp.session import SessionFailure
    _cli_file(monkeypatch, tmp_path)
    monkeypatch.setenv("DL16_BACKEND_MODE", "session")

    class FailedSession:
        calls = 0
        def request(self, request, *, timeout_s):
            self.calls += 1
            raise SessionFailure("SESSION_TIMEOUT", "response timed out")

    fake = FailedSession()
    monkeypatch.setattr(backend, "_get_session", lambda cli: fake)
    with patch("dl16_mcp.backend.subprocess.run", side_effect=AssertionError("must not fallback")) as run:
        result = backend.capture(CaptureRequest())
    assert result["error_code"] == "SESSION_TIMEOUT"
    assert fake.calls == 1
    assert run.call_count == 0


def test_native_capture_failure_closes_session_without_replay(monkeypatch, tmp_path):
    _cli_file(monkeypatch, tmp_path)
    monkeypatch.setenv("DL16_BACKEND_MODE", "session")

    class Session:
        def __init__(self):
            self.requests = 0
            self.closed = False
        def request(self, request, timeout_s):
            self.requests += 1
            return {"result": {"success": False, "error_code": "CAPTURE_TIMEOUT"}}
        def close(self):
            self.closed = True

    session = Session()
    monkeypatch.setattr(backend, "_get_session", lambda cli: session)
    result = backend.capture(CaptureRequest())
    assert session.requests == 1 and session.closed
    assert result["error_code"] == "CAPTURE_TIMEOUT"
    assert result["session_invalidated"] is True


def test_unvalidated_rle_is_not_silently_ignored(monkeypatch):
    monkeypatch.setattr(backend, "find_native_cli", lambda: (_ for _ in ()).throw(AssertionError("must not launch")))
    result = backend.capture(CaptureRequest(rle=True))
    assert result["error_code"] == "RLE_NOT_VALIDATED"
    assert result["evidence_source"] == "NONE"
