"""Offline safety tests for TASK-066 hardware harness; no USB calls."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "dl16_task066_hil.py"
spec = importlib.util.spec_from_file_location("dl16_task066_hil", SCRIPT)
assert spec and spec.loader
hil = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hil)


def test_default_is_offline_without_importing_device(monkeypatch, capsys):
    import builtins
    original_import = builtins.__import__

    def no_device_import(name, *args, **kwargs):
        if name == "dl16_mcp" or name.startswith("dl16_mcp."):
            raise AssertionError("offline plan must not import runtime/device modules")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_device_import)
    assert hil.main(["--case", "normal"]) == 0
    output = capsys.readouterr().out
    assert "HIL_NOT_RUN" in output
    assert "OFFLINE_PLAN_ONLY" in output


@pytest.mark.parametrize("name", hil.CASES)
def test_each_case_can_print_offline_plan(name, capsys):
    assert hil.main(["--case", name]) == 0
    assert name in capsys.readouterr().out


def test_execute_refuses_missing_operator_flags_before_usb(monkeypatch):
    monkeypatch.setattr(hil.sys.stdin, "isatty", lambda: True)
    assert hil.main(["--case", "pwm1-reject", "--execute"]) == 2


def test_execute_refuses_noninteractive_operator(monkeypatch):
    monkeypatch.setattr(hil.sys.stdin, "isatty", lambda: False)
    args = ["--case", "normal", "--execute"] + [
        "--" + n.replace("_", "-") for n in hil.FLAGS
    ]
    assert hil.main(args) == 2


def test_fault_injection_is_single_shot_and_restores_real_functions():
    events = []
    calls = []
    def real_pwm(out, action="configure", *args, **kwargs):
        calls.append(("pwm", out, action))
        return {"success": True}
    def real_capture(*args, **kwargs):
        calls.append(("capture",))
        return {"success": True}
    def real_poll(operation_id):
        calls.append(("poll", operation_id))
        return {"state": "finished"}
    svc = SimpleNamespace(logic_pwm=real_pwm, logic_capture=real_capture,
                          logic_stream_poll=real_poll)
    with hil.fault_injection(svc, "pwm1-reject", events):
        assert svc.logic_pwm(0, "configure")["success"]
        assert svc.logic_pwm(1, "configure")["success"] is False
        assert svc.logic_pwm(1, "configure")["success"] is True
        assert svc.logic_pwm(0, "stop")["success"] is True
    assert svc.logic_pwm is real_pwm
    assert svc.logic_capture is real_capture
    assert svc.logic_stream_poll is real_poll
    assert len(events) == 1
    assert ("pwm", 1, "configure") in calls  # second PWM1 call only


def test_injected_stream_poll_error_only_once():
    events = []
    def poll(operation_id):
        return {"state": "finished"}
    svc = SimpleNamespace(logic_pwm=lambda *a, **kw: {"success": True},
                          logic_capture=lambda *a, **kw: {"success": True},
                          logic_stream_poll=poll)
    with hil.fault_injection(svc, "stream-poll-error", events):
        assert svc.logic_stream_poll("op")["error_code"] == "TASK066_INJECTED_POLL_ERROR"
        assert svc.logic_stream_poll("op")["state"] == "finished"
    assert svc.logic_stream_poll is poll
