from unittest.mock import Mock

import pytest
from dl16_mcp import backend, server


@pytest.mark.parametrize("kwargs", [{}, {"confirm_safe_wiring": True, "output": 2},
    {"confirm_safe_wiring": True, "duty_percent": float("nan")},
    {"confirm_safe_wiring": True, "frequency_hz": True}])
def test_pwm_rejection_does_not_launch(monkeypatch, kwargs):
    launch = Mock(side_effect=AssertionError("must not launch"))
    monkeypatch.setattr(backend, "_get_session", launch)
    args = {"output": 0, **kwargs}
    assert backend.pwm(**args)["success"] is False
    launch.assert_not_called()


def test_pwm_requires_session_and_confirmed_wiring(monkeypatch):
    monkeypatch.delenv("DL16_BACKEND_MODE", raising=False)
    assert backend.pwm(0, confirm_safe_wiring=True)["error_code"] == "SESSION_MODE_REQUIRED"


def test_public_pwm_and_close_route_same_owner(monkeypatch, tmp_path):
    monkeypatch.setenv("DL16_BACKEND_MODE", "session")
    monkeypatch.setattr(backend, "find_native_cli", lambda: tmp_path / "cli")
    owner = Mock()
    owner.request.return_value = {"ok": True, "output": 0}
    monkeypatch.setattr(backend, "_get_session", lambda cli: owner)
    monkeypatch.setattr(backend, "_SESSION", owner)
    doc = server.logic_pwm(0, confirm_safe_wiring=True)
    assert doc["success"] and not doc["physical_output_verified"]
    owner.request.assert_called_once_with({"command": "pwm", "op": "configure", "output": 0,
                                          "frequency_hz": 1000, "duty_percent": 50.0}, timeout_s=10)
    assert server.logic_session_close()["closed"]
    owner.close.assert_called_once()
