# MCP tool reference (atk-logic-mcp-dl16)

Thin stdio MCP server (`src/dl16_mcp/server.py`) over deterministic service functions.
Live capture uses only the pinned native CLI; analysis/export/decode are offline.
Evidence is never upgraded implicitly: synthetic, derived, saved-vendor and
REAL_HARDWARE sources stay distinct.

## Tools

| Tool | Mode | Summary |
|---|---|---|
| `logic_status` | native (read-only) | Device model, firmware, USB speed, channel count, backend readiness. |
| `logic_capture` | native (buffer only) | Bounded capture to disk; returns integrity/ACK/complete flags and artifact dir. |
| `logic_inspect` | offline | Preview up to N edges with sample/time indices. |
| `logic_measure_skew` | offline | Signed pairwise delay, P95/P99, missing/extra pulses, waveform verdict. |
| `logic_measure_pwm` | offline | Median-period frequency, period jitter. |
| `logic_export` | offline | Write VCD / edge-CSV / sample-CSV of one channel; returns path. |
| `logic_filter` | offline | Glitch removal (drop short pulses) into a derived capture. |
| `logic_search` | offline | Sample positions matching multi-channel conditions. |
| `logic_decode` | offline | UART (parity/stop/invert), I2C, SPI (modes 0-3, bit order). |

### Parameters (abridged)

- `logic_capture(channels, sample_rate_hz, duration_ms, threshold_voltage, trigger, timeout_s)` —
  `trigger`: `immediate` or `chN:rising|falling|high|low|both` for an enabled channel.
  Buffer mode only; success requires `COMPLETE` + capture-complete + trigger-ACK.
- `logic_export(capture_id, channel, fmt="vcd"|"edges"|"samples", polarity, atkdl_file, out_name, overwrite)`.
- `logic_filter(capture_id, channel, min_pulse_samples, atkdl_file, out_name, overwrite)`.
- `logic_search(capture_id, conditions, limit, atkdl_file)` — conditions like
  `["ch7=rising","ch15=high"]` (AND, same sample).
- `logic_decode(capture_id, protocol, channels, baud_rate, cpol, cpha, data_bits, parity, stop_bits, invert, bit_order, bits_per_word)`.

## Native helper tools (not MCP; offline build via scripts)

- `atk-dl16.exe` — pinned capture CLI (used by `logic_capture`/`logic_status`).
- `dl16-vector-dump.exe` — offline CPP<->Python protocol cross-check.
- `dl16-pwm.exe` — bounded PWM0/PWM1 start/stop sender (`0x17`), operator-gated.

PWM output is **deliberately not an MCP tool**: it drives pins and stays a reviewed,
operator-invoked helper. No `send_raw`, firmware, bootloader or driver tool exists.

## Output discipline

Tools return bounded JSON and file paths, never full multi-MB waveforms in the
message. VCD/edge output is edge-based; sample-CSV is capped. Existing export and
derived-capture files are protected unless `overwrite=true`.

## Evidence tiers

`REAL_HARDWARE` (native capture), `SAVED_ATKDL` (vendor archive), `DERIVED` (filtered),
`SYNTHETIC` (tests) — never conflated. `PASS_WAVEFORM` is a numeric result, not an
instrument or end-to-end certification.

## Local CLI parity

`dl16ctl status|capture|skew|export|filter|search` cover the same offline functions
for local use; `logic_capture` is the only path that opens USB.
