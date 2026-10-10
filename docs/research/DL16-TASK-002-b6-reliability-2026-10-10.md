# DL16-TASK-002 gate B6 — repeat reliability / open-after-capture failure (2026-10-10)

Evidence tier: **LOCAL_HIL** on the owner's DL16 Plus (MCU v1.9, FPGA v2.22).
Wiring: PWM0 -> CH0 loopback. 20 sequential CH0 captures, 20 MHz, 10 ms, single
attempt each (no retry). Full evidence (ignored):
`artifacts/hil/DL16-TASK-002/b6-repeat.json`.

## Result

```
trials: 20   first-attempt success: 10   failures: 10
error codes: {"OK": 10, "PROTOCOL_ERROR": 10}
```

The failures are **deterministic and alternating**: trials 0,2,4,...,18 succeed;
trials 1,3,5,...,19 fail with `PROTOCOL_ERROR` ("Failed to parse FPGA device info
packet"). Success elapsed ~0.31 s; failure elapsed ~1.88 s.

## Interpretation

The `Device::open()` (FPGA device-info query) that **immediately follows a completed
capture** fails to parse; the following open succeeds. A single retry therefore
always recovers (our scripts already retry; effective success 100 %).

This is the R3 short/non-2048B **device-info reply** desync, now characterized as
state-dependent rather than random: a capture leaves the device-info query in a
state that fails once.

## Impact

- The MCP/CLI capture path, invoked once, would fail ~50 % of the time on this
  firmware.
- A bounded retry of the CLI invocation (not a USB reset) on this specific error
  raises effective reliability to 100 %.

## Status

- B6: `LOCAL_HIL` — raw reliability 50 %; retry-contained.
- No USB reset, driver change or power cycle used (AGENTS.md honored).
