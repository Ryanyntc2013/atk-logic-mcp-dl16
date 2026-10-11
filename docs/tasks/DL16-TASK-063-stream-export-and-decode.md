# DL16-TASK-063 — Stream capture artifacts export and offline analysis integration

State: **DONE (implemented, verified with synthetic tests and confirmed against physical Stream capture)**.
Base: `fec9d12`. Pinned native CLI + single physical owner verification.

## Objective

In TASK-060, TASK-061, and TASK-062, multi-read carry-over buffering, live cancellation, and the sample rate ladder (1MHz to 20MHz) were validated on physical hardware, saving 16-channel `.packed.bin` files and `stream_meta.json`.
TASK-063's objective was to:
1. Extend `dl16_mcp.artifacts.load_capture` to automatically recognize Stream capture directories containing `stream_meta.json` and `ch{channel}.packed.bin`.
2. Construct valid `Waveform` instances preserving `integrity: "INCOMPLETE"` and `evidence_source`.
3. Integrate Stream captures with existing analysis and export pipelines:
   - `logic_inspect`: edge preview and transitions.
   - `logic_measure_pwm`: median period, frequency, and jitter measurements.
   - `logic_export`: VCD, edge CSV, and sample CSV export.
   - `logic_decode`: UART, I2C, and SPI protocol decoding.
   - `logic_filter`: glitch filtering.
   - `logic_search`: multi-channel logic level searching.
4. Verify offline with synthetic tests and physically against captured 1000ms PWM hardware streams.

## Implementation details

- `src/dl16_mcp/artifacts.py`:
  - Added detection of `stream_meta.json` in `load_capture`.
  - Loaded `ch{channel}.packed.bin` as 1-bit-per-sample raw byte data (`samples = len(raw) * 8`).
  - Preserved `data_integrity: "INCOMPLETE"` and original metadata.
- `tests/test_artifacts.py`:
  - Added `test_load_stream_capture` verifying stream capture loading and missing channel error checking.

## Verification results

- Synthetic regression:
  - `python -m pytest -q`: 308 passed in 15.39s.
  - `python -m compileall -q src`: clean (0 errors).
- Physical verification against TASK-060 physical capture (`experimental-stream-0cd90958ea1e4d369b9aa2b1c54d1cd7`):
  - CH8 (PWM0 1kHz): `cycles: 991, frequency_hz_median: 1000.0, period_ns_jitter_rms: 0.0`.
  - CH14 (PWM1 2kHz): `cycles: 1982, frequency_hz_median: 2000.0, period_ns_jitter_rms: 0.0`.
  - VCD export: exported 991,616 samples to `.vcd` (31,636 bytes), integrity marked `INCOMPLETE`.
  - Edge inspection: 992 edges detected with exactly 1,000 samples (1.0ms) between rising edges.
