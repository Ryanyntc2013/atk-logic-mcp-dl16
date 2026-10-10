"""Standard MCP stdio server, thin adapter over deterministic service functions."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from . import service

mcp = FastMCP("atk-logic-mcp-dl16")


@mcp.tool()
def logic_status() -> dict:
    """Query connected ATK-DL16/DL16 Plus and native backend readiness."""
    return service.logic_status()


@mcp.tool()
def logic_capture(channels: list[int] | None = None, sample_rate_hz: int = 20_000_000,
                  duration_ms: int = 20, threshold_voltage: float = 1.6,
                  trigger: str = "immediate", timeout_s: float = 45.0) -> dict:
    """Capture to disk using native CLI. No simulated waveform ever returned as hardware.

    Buffer mode only. Trigger physical effectiveness must still be verified by HIL.
    """
    return service.logic_capture(channels, sample_rate_hz, duration_ms,
                                 threshold_voltage, trigger, timeout_s)


@mcp.tool()
def logic_inspect(capture_id: str, channel: int, max_edges: int = 50,
                  polarity: str = "rising", atkdl_file: str | None = None) -> dict:
    """Inspect digital edge positions and timestamps in a saved capture."""
    return service.logic_inspect(capture_id, channel, max_edges, polarity, atkdl_file)


@mcp.tool()
def logic_measure_skew(capture_id: str, reference_channel: int, target_channel: int,
                       polarity: str = "rising", expected_delay_ns: float = 0.0,
                       match_window_ns: float | None = None,
                       max_abs_error_ns: float | None = None,
                       atkdl_file: str | None = None) -> dict:
    """Measure signed pulse-to-pulse skew and missed pulses between channels.

    Returns PASS_WAVEFORM/FAIL_WAVEFORM, never claims calibrated instrument accuracy.
    """
    return service.logic_measure_skew(capture_id, reference_channel, target_channel,
                                      polarity, expected_delay_ns, match_window_ns,
                                      max_abs_error_ns, atkdl_file)


@mcp.tool()
def logic_measure_pwm(capture_id: str, channel: int, atkdl_file: str | None = None) -> dict:
    """Median-period frequency and jitter analysis on a saved channel."""
    return service.logic_measure_pwm(capture_id, channel, atkdl_file)


@mcp.tool()
def logic_export(capture_id: str, channel: int, fmt: str = "vcd",
                 polarity: str = "rising", atkdl_file: str | None = None,
                 out_name: str | None = None) -> dict:
    """Export one channel to a compact VCD or edge CSV file; returns the path, not the bytes.

    Edge-based output stays bounded for large captures; open the file with sigrok or
    any waveform viewer. It never adds device or timing certification.
    """
    return service.logic_export(capture_id, channel, fmt, polarity, atkdl_file, out_name)


@mcp.tool()
def logic_filter(capture_id: str, channel: int, min_pulse_samples: int,
                 atkdl_file: str | None = None, out_name: str | None = None) -> dict:
    """Write a derived capture with pulses shorter than min_pulse_samples removed."""
    return service.logic_filter(capture_id, channel, min_pulse_samples, atkdl_file, out_name)


@mcp.tool()
def logic_search(capture_id: str, conditions: list, limit: int = 100,
                 atkdl_file: str | None = None) -> dict:
    """Find samples where every condition holds, e.g. ["ch7=rising", "ch15=high"]."""
    return service.logic_search(capture_id, conditions, limit, atkdl_file)


@mcp.tool()
def logic_decode(capture_id: str, protocol: str, channels: list[int],
                 baud_rate: int = 115200, cpol: int = 0, cpha: int = 0,
                 atkdl_file: str | None = None) -> dict:
    """Decode UART, I2C or SPI via pinned upstream decoder after native bootstrap."""
    return service.logic_decode(capture_id, protocol, channels, baud_rate, cpol, cpha, atkdl_file)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
