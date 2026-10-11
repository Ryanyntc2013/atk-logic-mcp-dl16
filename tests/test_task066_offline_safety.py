"""TASK-066: offline-only regressions. Never open USB or invoke a native binary."""
from __future__ import annotations

import hashlib
import json

import numpy as np
import pytest

from dl16_mcp import backend, service
from dl16_mcp.artifacts import Waveform, load_capture
from dl16_mcp.config import CaptureRequest
from dl16_mcp.decoders import decode_uart


def capture(monkeypatch, tmp_path, cid="original", *, integrity="COMPLETE"):
    monkeypatch.setenv("DL16_DATA_DIR", str(tmp_path))
    folder = tmp_path / "captures" / cid
    folder.mkdir(parents=True)
    raw = b"\x03\x0c"
    (folder / "ch00.bits").write_bytes(raw)
    metadata = {"capture_id": cid, "sample_rate": 1_000_000,
                "requested_samples": 16, "sample_counts": {"0": 16},
                "data_integrity": integrity,
                "capture_complete_received": integrity == "COMPLETE",
                "trigger_ack_received": integrity == "COMPLETE",
                "evidence_source": "SYNTHETIC"}
    (folder / "meta.json").write_text(json.dumps(metadata), encoding="utf-8")
    return folder, raw


def test_filter_never_overwrites_original_even_with_override(monkeypatch, tmp_path):
    folder, original = capture(monkeypatch, tmp_path)
    before_meta = (folder / "meta.json").read_bytes()
    result = service.logic_filter("original", 0, 3, out_name="original", overwrite=True)
    assert result["success"] is False
    assert (folder / "ch00.bits").read_bytes() == original
    assert (folder / "meta.json").read_bytes() == before_meta


def test_filter_never_overwrites_an_existing_capture(monkeypatch, tmp_path):
    capture(monkeypatch, tmp_path)
    other, contents = capture(monkeypatch, tmp_path, cid="another")
    res = service.logic_filter("original", 0, 3, out_name="another", overwrite=True)
    assert res["success"] is False
    assert (other / "ch00.bits").read_bytes() == contents


def test_filter_preserves_source_integrity_and_sha(monkeypatch, tmp_path):
    _, original = capture(monkeypatch, tmp_path, integrity="UNVERIFIED")
    res = service.logic_filter("original", 0, 3, out_name="derived")
    assert res["success"] is True
    m = json.loads((tmp_path / "captures" / "derived" / "meta.json").read_text())
    assert m["source_integrity"] == "UNVERIFIED"
    assert m["source_sha256"] == hashlib.sha256(original).hexdigest()
    assert m["data_integrity"] != "COMPLETE"
    assert m["capture_complete_received"] is False
    assert m["trigger_ack_received"] is False
    assert m["processing_status"] == "COMPLETE"
    assert load_capture("derived", 0).integrity == "UNVERIFIED"


def test_filter_of_complete_source_keeps_original_evidence(monkeypatch, tmp_path):
    capture(monkeypatch, tmp_path)
    res = service.logic_filter("original", 0, 3, out_name="derived")
    assert res["success"] is True
    m = json.loads((tmp_path / "captures" / "derived" / "meta.json").read_text())
    assert m["capture_complete_received"] is True
    assert m["trigger_ack_received"] is True
    assert m["source_evidence_source"] == "SYNTHETIC"


def test_uart_back_to_back_bytes_do_not_create_false_frames():
    # 8N1 at 10 samples/bit, no idle gaps between 0x6B DE F6 49.
    values = [0x6B, 0xDE, 0xF6, 0x49]
    bits = [1] * 10
    for value in values:
        bits += [0] * 10
        for b in range(8):
            bits += [((value >> b) & 1)] * 10
        bits += [1] * 10
    bits += [1] * 10
    raw = np.packbits(np.asarray(bits, dtype=np.uint8), bitorder="little").tobytes()
    wave = Waveform(1, raw, len(bits), 1_000_000, "COMPLETE", "SYNTHETIC", {})
    got = decode_uart(wave, baud_rate=100_000)
    assert [x["value"] for x in got] == values
    assert all(x["parity_ok"] and x["stop_ok"] for x in got)


def test_duplicate_channel_and_trigger_rejected():
    with pytest.raises(ValueError, match="Duplicate"):
        CaptureRequest(channels=(0,), trigger="ch0:rising,ch0:falling").validate()


def test_host_timeout_budget_rejected_before_device(monkeypatch):
    monkeypatch.setattr(backend, "find_native_cli", lambda: pytest.fail("native launched"))
    result = backend.capture(CaptureRequest(channels=(0,), trigger="ch0:rising"),
                             timeout_s=12, trigger_timeout_sec=10)
    assert result["error_code"] == "INVALID_CAPTURE_CONFIG"


def test_stream_explicit_valid_samples_and_untrusted_padding(monkeypatch, tmp_path):
    monkeypatch.setenv("DL16_DATA_DIR", str(tmp_path))
    folder = tmp_path / "captures" / "stream"
    folder.mkdir(parents=True)
    (folder / "ch8.packed.bin").write_bytes(b"\x00\x7f")
    metadata = {"sample_rate_hz": 1_000_000, "data_integrity": "INCOMPLETE",
                "evidence_source": "SYNTHETIC_OFFLINE",
                "channels": [{"channel": 8, "valid_samples": 13}]}
    (folder / "stream_meta.json").write_text(json.dumps(metadata))
    wave = load_capture("stream", 8)
    assert wave.samples == 13
    assert wave.metadata["sample_count_authority"] == "EXPLICIT_VALID_SAMPLES"
    metadata["channels"] = [{"channel": 8}]
    metadata["data_integrity"] = "COMPLETE"
    (folder / "stream_meta.json").write_text(json.dumps(metadata))
    wave = load_capture("stream", 8)
    assert wave.samples == 16
    assert wave.integrity == "UNVERIFIED"


def _selftest_setup(monkeypatch):
    monkeypatch.setattr(backend, "has_owned_session", lambda: False)
    monkeypatch.setattr(service, "logic_status",
                        lambda: {"connected": True, "ready": True, "details": {"model": "DL16 Plus"}})


def test_selftest_refuses_to_preempt_other_owner(monkeypatch):
    monkeypatch.setattr(backend, "has_owned_session", lambda: True)
    monkeypatch.setattr(service, "logic_status", lambda: pytest.fail("hardware accessed"))
    result = service.logic_self_test(confirm_safe_wiring=True)
    assert result["error_code"] == "SESSION_ALREADY_OWNED"


def test_selftest_partial_pwm_failure_always_stops_and_closes(monkeypatch):
    _selftest_setup(monkeypatch)
    calls = []
    def pwm(output, action="configure", *args, **kwargs):
        calls.append((output, action))
        if action == "configure" and output == 1:
            return {"success": False, "error_code": "SIMULATED"}
        return {"success": True}
    monkeypatch.setattr(service, "logic_pwm", pwm)
    monkeypatch.setattr(service, "logic_session_close", lambda: calls.append(("close",)) or {"success": True})
    monkeypatch.setattr(service, "logic_capture", lambda **k: pytest.fail("capture should not start"))
    result = service.logic_self_test(confirm_safe_wiring=True)
    assert result["error_code"] == "PWM_CONFIG_FAILED"
    assert (0, "stop") in calls and (1, "stop") in calls and ("close",) in calls
    assert result["cleanup_ok"] is True


def test_selftest_failed_pwm_cleanup_never_returns_healthy(monkeypatch):
    _selftest_setup(monkeypatch)
    def pwm(output, action="configure", *args, **kwargs):
        return {"success": action == "configure" and output == 0}
    monkeypatch.setattr(service, "logic_pwm", pwm)
    monkeypatch.setattr(service, "logic_session_close", lambda: {"success": False})
    result = service.logic_self_test(confirm_safe_wiring=True)
    assert result["success"] is False
    assert result["cleanup_ok"] is False
    assert result["overall_health"] == "UNVERIFIED_CLEANUP"


def test_selftest_stream_poll_error_requests_cancel(monkeypatch):
    _selftest_setup(monkeypatch)
    actions = []
    monkeypatch.setattr(service, "logic_pwm", lambda *a, **kw: {"success": True})
    monkeypatch.setattr(service, "logic_capture", lambda **kw: {"success": True, "capture_id": "buffer"})
    monkeypatch.setattr(service, "logic_measure_pwm",
                        lambda cid, ch: {"frequency_hz_median": 1000 if ch == 8 else 2000})
    monkeypatch.setattr(service, "logic_session_close", lambda: actions.append("close") or {"success": True})
    monkeypatch.setattr(service, "logic_stream_start", lambda **kw: {"operation_id": "op42"})
    monkeypatch.setattr(service, "logic_stream_poll",
                        lambda operation_id: {"success": False, "error_code": "SIMULATED"})
    monkeypatch.setattr(service, "logic_stream_cancel",
                        lambda operation_id: actions.append("cancel") or {"success": True})
    result = service.logic_self_test(confirm_safe_wiring=True)
    assert result["success"] is False
    assert "cancel" in actions
    assert "close" in actions
    assert result["cleanup_ok"] is False
