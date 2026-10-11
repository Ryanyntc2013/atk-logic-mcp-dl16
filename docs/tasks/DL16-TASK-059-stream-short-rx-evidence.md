# DL16-TASK-059 — physical short-RX raw frame reproduction and analysis

State: **DONE (physical evidence reproduced, captured and analyzed)**.
Base: `d683354`. Single parent-owned physical run executed under authorized hardware conditions.

## Objective and hardware execution

In TASK-057, a 1MHz/1000ms experimental Stream run terminated with `SHORT_RX` (1024 short bytes) after 65024 packed bytes (29 reads), before cancellation occurred.
TASK-058 added optional bounded `dl16-raw-rx/v1` logging to the experimental Stream path.
TASK-059's objective was to run ONE bounded 1MHz/1000ms Stream capture with `raw_rx_logging=True` to reproduce the short-read condition and capture the complete raw USB bytes into `rx.bin` for exact framing analysis.

Execution parameters:
- Device: DL16 Plus, VID:PID `1A86:FFCC`, single owner, ATK-Logic GUI closed.
- Backend: `DL16_BACKEND_MODE=session`, `DL16_CLI_PATH` using rebuilt pinned native binary.
- Operation: `backend.stream_start(experimental_opt_in=True, safety_confirmation="CONFIRMED_SAFE_WIRING_GUI_CLOSED", channels=[8, 14], sample_rate_hz=1000000, duration_ms=1000, threshold_voltage=1.6, raw_rx_logging=True, raw_rx_max_bytes=33554432)`.
- Cleanup: stop attempted and confirmed true; session closed successfully.

## Findings and exact evidence

Result summary from `artifacts/hil/DL16-TASK-059/result.json`:
- `reason`: `"SHORT_RX"`
- `stored_bytes`: 123952
- `reads`: 32
- `short_bytes`: 512
- `receive_elapsed_ns`: 55366300 (55.3 ms)
- `order3_raw_hex`: received
- `trigger_ack_received`: true
- `cleanup_stop_attempted`: true, `cleanup_stop_ok`: true
- Raw log: `rx.bin` size 523,016 bytes, 32 records, `closed=true`, `error=""`.

Exact record analysis of `rx.bin`:
1. Magic header: `DL16RX01` (8 bytes).
2. Records 0 through 30: each exactly 16,384 bytes (8 full 2048-byte banks), `ErrorCode::Ok`.
3. Record 31: exactly 14,848 bytes, `ErrorCode::Ok`.
   - 14,848 bytes = 7 * 2048 bytes (14,336 bytes) + 512 bytes remainder.
   - 14,848 bytes is an exact multiple of 512 bytes (29 USB bulk packets of 512 bytes).
   - The 512-byte tail starts with `0a 01` (Order 1 ChannelData packet header), representing lane 0 of the 8th bank.
   - `read_bulk` returned `Error::ok()` because libusb returned `LIBUSB_ERROR_TIMEOUT` after transferring 29 packets (a non-fatal timeout).

## Root cause analysis

The fail-closed rule in `scripts/experimental_stream.h`:
```cpp
size_t aligned = n / 2048 * 2048;
result.short_bytes += n - aligned;
if (n != aligned) { result.reason = "SHORT_RX"; break; }
```
aborts the stream whenever a single `read_bulk` call returns a number of bytes that is not an exact multiple of 2048 bytes.
Because USB 2.0 High-Speed bulk transfers operate with packet size 512 bytes, a read with a timeout (e.g. 10ms) naturally completes on a 512-byte packet boundary (e.g. 14,848 bytes) rather than waiting for a full 2048-byte bank.
The device did NOT fail and the data was NOT corrupted; the remaining 1536 bytes of that bank would have arrived in the subsequent USB read.

Evidence location: `artifacts/hil/DL16-TASK-059/` (`result.json`, `records.json`, `native-hash.txt`, `journal/`).
Raw capture artifact: `artifacts/captures/experimental-stream-9b8e442e135a4956b2feecbb305b221a/rx.bin`.
