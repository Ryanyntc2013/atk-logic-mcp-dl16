# DL16-TASK-010 — 9-byte vs 10-byte SimpleTrigger gating (R2 decision gate)

**Date:** 2026-10-10
**Evidence tier:** LOCAL_HIL on the owner's DL16 Plus (MCU v1.9, FPGA v2.22, USB 2.0).
**Tool:** `tests/native/trigger_tool.cpp` (`dl16-trigger`), an operator-approved,
bounded probe that sends ParameterSetting then a selectable SimpleTrigger payload,
reads RX for a bounded window, and sends Stop on exit.
**Result: the 10-byte payload gates; the 9-byte payload does not.**

## Method

Same ParameterSetting (Buffer, 20 MHz, 20 ms, 1.6 V, position 50 %), same channel;
only the SimpleTrigger payload layout is varied:

- 9B: 8 channel-pair bytes + 1 instant flag (VENDOR/CPP `build_simple_trigger_frame`).
- 10B: 8 channel-pair bytes + 2 collect-type bytes `00 00` (LHX/HUGEL).

Completion is the order-6 Complete message within the read window; an order-4 ACK
(status 3) is required but not sufficient.

## Observations

| Payload | Condition | Channel signal | Completed | Elapsed | ACK | order-3 offset |
|---|---|---|---|---:|---|---|
| 9B | rising | CH0, no edges | **yes** | 46 ms | yes | yes |
| 10B | rising | CH0, no edges | **no (waited)** | 5000 ms | yes | no |
| 10B | rising | CH8, PWM edges | yes | 22 ms | yes | yes |
| 9B | rising | CH8, PWM edges | yes | 46 ms | yes | yes |
| 10B | high | CH0, held low | **no (waited)** | 3000 ms | yes | no |
| 9B | high | CH0, held low | yes | 45 ms | yes | yes |
| 10B | low | CH0, held low | yes | 22 ms | yes | yes |

(CH0 is not wired; CH8 carries a PWM0 1 kHz loopback during the edge-present rows.)

## Conclusion

- The **10-byte** SimpleTrigger payload performs **real gating**: with the condition
  unmet it waits (no Complete, no order-3 offset) and with the condition met it
  completes. Edge and level conditions behave correctly.
- The pinned **9-byte** payload does **not** gate: it completes immediately even with
  no edge, regardless of the requested condition. This confirms the B3 observation and
  resolves research **R2**.
- An order-4 ACK + non-zero order-3 offset from a 9B capture are therefore **not**
  trigger evidence.

## Impact / fix (DL16-TASK-011)

- The pinned CPP `build_simple_trigger_frame` used the 9-byte layout, so MCP
  `logic_capture` did **not** gate. `bootstrap-native.ps1` now applies a **tracked
  patch** to the ignored checkout: non-immediate triggers use the 10-byte gating
  payload, immediate keeps the 9-byte instant flag. The offline reference, golden
  vectors and native cross-check harness were updated to match.
- **HIL after the fix (this unit):**
  - CH0 (no edge) + `ch0:rising` -> `CAPTURE_TIMEOUT` (gated, waits) — via MCP CLI.
  - CH8 (PWM0 edges) + `ch8:rising` -> success.
  - CH0 + `immediate` -> success (regression OK).
- The pinned commit content is never modified on disk permanently; the patch is
  applied at build time and is idempotent.

## Reproduce

```powershell
# CH0 currently unwired; PWM0 -> CH8 loopback when an edge is desired.
.\tests\native\build\Release\dl16-trigger.exe 9b 0 rising 5000
.\tests\native\build\Release\dl16-trigger.exe 10b 0 rising 5000
```
