"""Standard MCP stdio server, thin adapter over deterministic service functions."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from . import service

mcp = FastMCP("atk-logic-mcp-dl16")


@mcp.tool()
def logic_export_atkdl(capture_id: str, channels: list[int], out_name: str) -> dict:
    """Write experimental offline-reader .atkdl subset; GUI compatibility UNVERIFIED."""
    return service.logic_export_atkdl(capture_id, channels, out_name)


@mcp.tool()
def logic_sigrok(vcd_file: str, decoder: str, channels: dict[str, int],
                 options: dict[str, str] | None = None, timeout_s: float = 30) -> dict:
    """Decode a saved VCD through optional sigrok-cli with bounded output; no USB access."""
    return service.logic_sigrok(vcd_file, decoder, channels, options, timeout_s)


@mcp.tool()
def logic_pwm(output: int, action: str = "configure", frequency_hz: int = 1000,
              duty_percent: float = 50.0, confirm_safe_wiring: bool = False) -> dict:
    """Drive a confirmed safe PWM output in the owned session; no raw commands.

    A successful write does not verify physical output. Session close stops owned outputs.
    """
    return service.logic_pwm(output, action, frequency_hz, duty_percent, confirm_safe_wiring)


@mcp.tool()
def logic_session_close() -> dict:
    """Close the owned native session and stop its owned PWM outputs; never replay capture."""
    return service.logic_session_close()


@mcp.tool()
def logic_status() -> dict:
    """Query connected ATK-DL16/DL16 Plus and native backend readiness."""
    return service.logic_status()


@mcp.tool()
def logic_capture(channels: list[int] | None = None, sample_rate_hz: int = 20_000_000,
                  duration_ms: int = 20, threshold_voltage: float = 1.6,
                  trigger: str = "immediate", timeout_s: float = 45.0,
                  trigger_position_percent: float | None = None,
                  trigger_timeout_sec: int | None = None) -> dict:
    """Capture to disk using native CLI. No simulated waveform ever returned as hardware.

    Buffer mode only. Edge/level and multi-channel AND triggers gate on this firmware
    (10-byte payload). trigger_position_percent sets the pre-trigger position;
    trigger_timeout_sec bounds the device trigger wait (default 30 s).
    """
    return service.logic_capture(channels, sample_rate_hz, duration_ms,
                                 threshold_voltage, trigger, timeout_s,
                                 trigger_position_percent, trigger_timeout_sec)


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
                 out_name: str | None = None, overwrite: bool = False) -> dict:
    """Export one channel as VCD, edge CSV or full sample CSV; returns the path.

    Edge-based output stays bounded; sample CSV is capped. Existing files are
    protected unless overwrite=true.
    """
    return service.logic_export(capture_id, channel, fmt, polarity, atkdl_file, out_name, overwrite)


@mcp.tool()
def logic_filter(capture_id: str, channel: int, min_pulse_samples: int,
                 atkdl_file: str | None = None, out_name: str | None = None,
                 overwrite: bool = False) -> dict:
    """Write a derived capture with pulses shorter than min_pulse_samples removed."""
    return service.logic_filter(capture_id, channel, min_pulse_samples, atkdl_file, out_name, overwrite)


@mcp.tool()
def logic_search(capture_id: str, conditions: list, limit: int = 100,
                 atkdl_file: str | None = None) -> dict:
    """Find samples where every condition holds, e.g. ["ch7=rising", "ch15=high"]."""
    return service.logic_search(capture_id, conditions, limit, atkdl_file)


@mcp.tool()
def logic_decode(capture_id: str, protocol: str, channels: list[int],
                 baud_rate: int = 115200, cpol: int = 0, cpha: int = 0,
                 atkdl_file: str | None = None, data_bits: int = 8, parity: str = "none",
                 stop_bits: int = 1, invert: bool = False, bit_order: str = "msb",
                 bits_per_word: int = 8) -> dict:
    """Decode UART (parity/stop/invert), I2C, or SPI (modes 0-3, bit order) offline."""
    return service.logic_decode(capture_id, protocol, channels, baud_rate, cpol, cpha,
                                atkdl_file, data_bits, parity, stop_bits, invert,
                                bit_order, bits_per_word)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
