import json
from pathlib import Path
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
