# DL16-TASK-061 — long Stream capture and live asynchronous cancellation

State: **DONE (verified with synthetic integration and confirmed via physical HIL run)**.
Base: `34777c2`. Single parent-owned physical run executed under authorized hardware conditions.

## Objective

In TASK-060, multi-read carry-over buffering solved the premature `SHORT_RX` abort on 512-byte bulk boundaries and completed a 1000ms stream.
TASK-061's objective was to:
1. Validate long Stream acquisition (5000ms planned duration) under real physical load.
2. Verify live cooperative cancellation in flight:
   - Poll atomic `progress` while streaming.
   - At $\ge 1\,\text{MB}$ stored data (~500ms~700ms in), issue `stream_cancel`.
   - Ensure the native worker exits cooperatively within tens of milliseconds without process killing or thread hanging.
   - Verify remaining banks are flushed to disk, unparsed bytes recorded, and terminal reason is strictly `"CANCELLED"`.
   - Confirm hardware stop frame is sent and acknowledged (`cleanup_stop_ok == True`).
   - Confirm the session and physical device remain responsive and reusable after cancellation.

## Implementation refinement

- `scripts/experimental_stream.h`:
  - Ensured `cancel.load()` strictly takes precedence in determining `result.reason = "CANCELLED"`.
  - Synced changes to `external/ATK-Logic-Mcp/cli/experimental_stream.h` and rebuilt `atk-dl16.exe`.

## Test verification

- Synthetic and regression suite:
  - 307 tests passed in 12.98s (`python -m pytest -q`).
  - Native compileall check clean (`python -m compileall -q src`).
  - Synthetic cancel test `test_actual_receive_incremental_all16_cancel_and_eof` passed.

## Physical HIL evidence

- Physical test run: 1MHz, 5000ms duration, channels 8 & 14 (with PWM0 at 1kHz and PWM1 at 2kHz), threshold 1.6V, `raw_rx_logging=True`.
- Device: DL16 Plus (VID:PID 1A86:FFCC, MCU v1.9, FPGA v2.22).
- Native executable SHA-256: recorded in `artifacts/hil/DL16-TASK-061/native-hash.txt`.
- Execution timeline:
  - Stream started with 5000ms deadline.
  - Progress polled: `stored_bytes` smoothly increased from 0 to 1,040,384 bytes across 92 USB bulk reads.
  - At 1,040,384 bytes, `logic_stream_cancel` was issued.
  - Native engine responded with non-blocking confirmation.
  - On the very next poll (~40ms later), the session had cleanly finished:
    - `reason`: `"CANCELLED"`
    - `reads`: 93
    - `records`: 93 in `rx.bin` (1,454,832 bytes total)
    - `stored_bytes`: 1,056,640 bytes total across 16 channels
    - `short_bytes`: 0
    - `order3_raw_hex`: received
    - `trigger_ack_received`: true
    - `cleanup_stop_attempted`: true, `cleanup_stop_ok`: true
  - Session reuse verified: `logic_status()` confirmed `connected: True` immediately following cancel.
  - Session closed cleanly: `{"success": true, "closed": true}`.
- Boundary evidence from `artifacts/hil/DL16-TASK-061/records.json`:
  - 6 reads ended on 512-byte boundaries with non-zero mod 2048 (Records 32, 34, 59, 61, 78, 80), all smoothly accumulated.
