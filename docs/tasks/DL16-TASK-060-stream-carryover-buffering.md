# DL16-TASK-060 — multi-read carry-over buffering for Stream capture

State: **DONE (implemented, verified with synthetic tests and confirmed via physical HIL run)**.
Base: `c05b80f`. Pinned native CLI + single physical owner verification.

## Objective

In TASK-059, exact physical evidence proved that USB 2.0 Bulk read timeouts naturally produce reads on 512-byte packet boundaries rather than full 2048-byte bank boundaries. The previous per-read alignment check aborted streaming with `SHORT_RX` whenever a read length was not an exact multiple of 2048 bytes.
TASK-060's objective was to:
1. Implement a persistent carry-over buffer (`std::vector<uint8_t> raw_carry`) across USB reads in `scripts/experimental_stream.h`.
2. Accumulate partial reads (< 2048 bytes) between consecutive USB bulk transfers, only submitting whole 2048-byte banks to decompression (`convert_to_pc`) and parsing (`RxParser`).
3. Handle terminal residue gracefully at session end without false-positive mid-stream aborts.
4. Verify with synthetic unit/integration tests (fragmented reads in 512-byte increments).
5. Execute an authorized single physical HIL capture (1MHz, 1000ms, all 16 channels, raw RX logging enabled) to confirm streaming continues past 512-byte USB read boundaries to full completion.

## Implementation details

- `scripts/experimental_stream.h`:
  - Replaced immediate per-read `n / 2048 * 2048` truncations with `raw_carry.insert(...)`.
  - Computed `size_t aligned = raw_carry.size() / 2048 * 2048`.
  - Converted and parsed only `aligned` bytes; erased processed bytes from `raw_carry`.
  - Accumulated non-fatal timeout reads with no data without prematurely aborting when `raw_carry` has partial data.
  - At terminal duration deadline, preserved unparsed partial bank bytes in `result.short_bytes += raw_carry.size()` while preserving reason `DEADLINE` when streaming succeeded.
- `tests/native/CMakeLists.txt`:
  - Ordered include paths to prioritize repository `scripts/` over external checkout headers.
- `tests/native/experimental_stream_test.cpp`:
  - Added `fragmented_512` mock mode delivering single 2048-byte banks chopped across four 512-byte USB reads.
- `tests/test_experimental_stream.py`:
  - Added `test_stream_carry_over_fragmented_512` verifying that 512-byte read fragments are seamlessly reassembled into complete channel streams.

## Test verification

- Synthetic and regression suite:
  - 307 tests passed in 12.33s (`python -m pytest -q`).
  - Native compileall check clean (`python -m compileall -q src`).
  - Native tests pass for both `dl16-experimental-stream-test` and `atkdl16_tests.exe`.

## Physical HIL evidence

- Physical test run: 1MHz, 1000ms duration, channels 8 & 14 (with PWM0 at 1kHz and PWM1 at 2kHz), threshold 1.6V, `raw_rx_logging=True`.
- Device: DL16 Plus (VID:PID 1A86:FFCC, MCU v1.9, FPGA v2.22).
- Native executable SHA-256: recorded in `artifacts/hil/DL16-TASK-060/native-hash.txt`.
- Results from `artifacts/hil/DL16-TASK-060/result.json`:
  - `reason`: `"DEADLINE"` (successfully completed full 1000ms duration, no `SHORT_RX` abort!).
  - `reads`: 152 USB bulk reads.
  - `records`: 152 records in `rx.bin` (2,389,192 bytes total).
  - `stored_bytes`: 1,983,232 bytes (123,952 bytes per channel across all 16 channels).
  - `short_bytes`: 0.
  - `order3_raw_hex`: received.
  - `trigger_ack_received`: true.
  - `cleanup_stop_attempted`: true, `cleanup_stop_ok`: true.
- Exact boundary evidence from `artifacts/hil/DL16-TASK-060/records.json`:
  - 8 separate reads ended on 512-byte boundaries with non-zero mod 2048:
    - Record 50: 15,872 bytes (mod 2048 = 1536)
    - Record 60: 512 bytes (mod 2048 = 512)
    - Record 119: 8,704 bytes (mod 2048 = 512)
    - Record 121: 7,680 bytes (mod 2048 = 1536)
    - Record 124: 9,728 bytes (mod 2048 = 1536)
    - Record 132: 14,848 bytes (mod 2048 = 512)
    - Record 147: 10,752 bytes (mod 2048 = 512)
    - Record 149: 5,632 bytes (mod 2048 = 1536)
  - Every single partial bank was accumulated across reads without dropping data or triggering false aborts.
