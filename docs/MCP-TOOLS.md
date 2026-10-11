# MCP tool reference (atk-logic-mcp-dl16)

Thin stdio MCP server (`src/dl16_mcp/server.py`) over deterministic service functions.
Live capture uses only the pinned native CLI; analysis/export/decode are offline.
Evidence is never upgraded implicitly: synthetic, derived, saved-vendor and
REAL_HARDWARE sources stay distinct.

## Tools

| Tool | Mode | Summary |
|---|---|---|
| `logic_pwm` | native (output; explicit confirmation) | Configure/stop one owned PWM output in the persistent session. |
| `logic_session_close` | native lifecycle | Close owned session/PWM with observable cleanup errors. |
| `logic_status` | native (read-only) | Device model, firmware, USB speed, channel count, backend readiness; session metadata is cached. |
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

## Experimental `.atkdl` writer

`logic_export_atkdl(capture_id, channels, out_name)` writes the known offline-reader ZIP subset with matching channel depth/rate and preserved provenance. Existing destinations are protected. Returns `gui_compatibility=UNVERIFIED`: successful reader roundtrip is NOT official GUI compatibility or physical capture certification.

## Optional sigrok host

`logic_sigrok(vcd_file, decoder, channels, options=None, timeout_s=30)` decodes a saved VCD through explicitly installed `sigrok-cli`. It does not capture USB traffic. Input is capped at 64 MiB; returned output preview at 64 KiB, stderr at 4 KiB. Missing binary returns `SIGROK_MISSING`. Decoder/channel/option identifiers are validated and no shell is invoked. External decoder catalogue is not certified; this environment has no installed sigrok-cli, so only offline mocked contract tests have run.

## Native helper tools (not MCP; offline build via scripts)

- `atk-dl16.exe` — pinned capture CLI (used by `logic_capture`/`logic_status`).
- `dl16-vector-dump.exe` — offline CPP<->Python protocol cross-check.
- `dl16-pwm.exe` — bounded PWM0/PWM1 start/stop sender (`0x17`), operator-gated.
- `dl16-trigger.exe` — bounded SimpleTrigger gating probe (9B/10B payload), operator-gated.

PWM output is now exposed as `logic_pwm(output, action="configure"|"stop", frequency_hz=1000, duty_percent=50, confirm_safe_wiring=false)`. It requires explicit safe-wiring confirmation, `DL16_BACKEND_MODE=session`, and native hello advertising `pwm`. Range: outputs 0/1, integer 1..20 MHz, finite duty 0..100%. A successful transfer does not prove physical output. Configure multiple outputs and capture within the same persistent owner; `logic_session_close()` stops owned outputs and surfaces cleanup failures.

`logic_self_test(safety_confirmation)` is a breaking rename of the old boolean `confirm_safe_wiring` parameter. The required value is the exact string `CONFIRMED_SAFE_WIRING_GUI_CLOSED`. `logic_pwm` still uses `confirm_safe_wiring`.

CLI: `dl16ctl pwm configure --output 0 --frequency-hz 1000 --duty-percent 50 --confirm-safe-wiring`, `dl16ctl pwm stop --output 0 --confirm-safe-wiring`, `dl16ctl session-close`. Standalone CLI exit closes its owner and stops owned outputs; use persistent MCP/native JSONL for setup followed by capture. No `send_raw`, firmware, bootloader or driver tool exists.

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
