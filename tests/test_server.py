import asyncio

from dl16_mcp import server

EXPECTED_TOOLS = {
    "logic_status",
    "logic_capture",
    "logic_inspect",
    "logic_measure_skew",
    "logic_measure_pwm",
    "logic_export",
    "logic_filter",
    "logic_search",
    "logic_decode",
}


def test_all_mcp_tools_registered():
    tools = asyncio.run(server.mcp.list_tools())
    names = {tool.name for tool in tools}
    missing = EXPECTED_TOOLS - names
    assert not missing, f"Missing MCP tools: {sorted(missing)}"


def test_no_raw_or_firmware_tools_exposed():
    tools = asyncio.run(server.mcp.list_tools())
    names = {tool.name.lower() for tool in tools}
    forbidden = {"send_raw", "flash", "firmware", "bootloader", "write_raw", "pwm"}
    assert names.isdisjoint(forbidden)
