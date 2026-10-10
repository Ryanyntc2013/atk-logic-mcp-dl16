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

## Impact / next

- The pinned CPP `build_simple_trigger_frame` uses the 9-byte layout, so the current
  MCP `logic_capture` does **not** gate. Fixing it requires a **reviewed patch or
  pinned fork** (change the non-immediate trigger payload to the 10-byte form) plus
  regression tests and local HIL — not a silent switch. Immediate-trigger semantics
  (9B `instant flag`) must be preserved and re-verified.
- No live encoding was changed by this task.

## Reproduce

```powershell
# CH0 currently unwired; PWM0 -> CH8 loopback when an edge is desired.
.\tests\native\build\Release\dl16-trigger.exe 9b 0 rising 5000
.\tests\native\build\Release\dl16-trigger.exe 10b 0 rising 5000
```
