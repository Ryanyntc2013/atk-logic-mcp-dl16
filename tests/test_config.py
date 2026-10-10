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
