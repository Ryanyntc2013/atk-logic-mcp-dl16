import pytest

from dl16_mcp.config import CaptureRequest


def test_immediate_trigger_ok():
    CaptureRequest().validate()


def test_multi_channel_trigger_ok():
    CaptureRequest(channels=(0, 8), trigger="ch8:rising,ch0:high").validate()


def test_trigger_requires_enabled_channel():
    with pytest.raises(ValueError):
        CaptureRequest(channels=(0,), trigger="ch8:rising").validate()


def test_bad_trigger_kind_rejected():
    with pytest.raises(ValueError):
        CaptureRequest(channels=(0,), trigger="ch0:bogus").validate()


def test_default_channel_cap_refuses_wide_capture(monkeypatch):
    import pytest
    from dl16_mcp.config import CaptureRequest
    monkeypatch.delenv("DL16_MAX_CHANNELS", raising=False)
    with pytest.raises(ValueError):
        CaptureRequest(channels=(0, 1, 2, 3, 4)).validate()
    CaptureRequest(channels=(0, 1, 2, 3)).validate()


def test_operator_override_raises_cap(monkeypatch):
    from dl16_mcp.config import CaptureRequest
    monkeypatch.setenv("DL16_MAX_CHANNELS", "16")
    CaptureRequest(channels=tuple(range(16))).validate()


def test_invalid_override_rejected(monkeypatch):
    import pytest
    from dl16_mcp.config import CaptureRequest
    monkeypatch.setenv("DL16_MAX_CHANNELS", "99")
    with pytest.raises(ValueError):
        CaptureRequest(channels=(0,)).validate()
