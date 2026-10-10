import pytest


def test_mcp_registers_expected_tools_when_sdk_available():
    pytest.importorskip("mcp", reason="MCP SDK is optional in isolated offline test environments")
    from dl16_mcp import server
    names = ["logic_status", "logic_capture", "logic_inspect", "logic_measure_skew",
             "logic_measure_pwm", "logic_decode"]
    for name in names:
        assert callable(getattr(server, name))
    assert hasattr(server.mcp, "run")
