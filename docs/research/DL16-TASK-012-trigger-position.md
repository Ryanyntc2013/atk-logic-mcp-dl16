# DL16-TASK-012 — trigger position (pre-trigger %) control

**Date:** 2026-10-10
**State:** DONE (exposed) / alignment certification deferred to B4.

## What changed

The pinned CLI hardcoded trigger position to 10 %. `scripts/bootstrap-native.ps1`
now applies a tracked patch to the ignored `cli/main.cpp` adding
`--trigger-position <percent>`; `backend.capture`, `logic_capture`,
`dl16ctl capture --trigger-position`, and the MCP `logic_capture` tool pass it
through (default: device 10 %).

## HIL evidence (LOCAL_HIL)

PWM0 -> CH8 (1 kHz). `dl16ctl`/MCP capture on CH8 `ch8:rising`, 20 MHz, 20 ms:

| `--trigger-position` | meta `trigger_position_percent` | order-3 `trigger_offset` |
|---:|---:|---:|
| 10 | 10 | 360007 |
| 50 | 50 | 200008 |

The order-3 offset tracks `total - trigger_depth`, confirming the parameter
reaches the device and changes the pre/post split.

## Caveat

The final pre-trigger **alignment** of the returned buffer (whether the trigger
edge lands at `trig_depth`) was not independently certified here — observed first
rising edge was 20 000 samples in both cases. That is a **B4** (order-3/tail/crop)
question and remains open. No absolute timing/uncertainty claim is made.

## Patch

Tracked and idempotent, applied by `bootstrap-native.ps1`; the pinned commit content
is never claimed modified. Offline tests cover the command plumbing
(`tests/test_backend.py`).
