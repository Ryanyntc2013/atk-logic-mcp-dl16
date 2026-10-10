# DL16-TASK-004 — PWM output configuration

**Owner:** local Codex/Cursor agent on Windows.
**State at issue:** OFFLINE_CODEC DONE / LIVE_NOT_RUN.
**Depends on:** DL16-TASK-002 (protocol vectors) and DL16-TASK-001 (device baseline).
**Research:** [`docs/research/DL16-TASK-002-pwm-output.md`](../research/DL16-TASK-002-pwm-output.md).

## Mission

Add reproducible PWM **output** configuration for the DL16's two PWM outputs
(commands `0x17`), independently implemented and offline-tested, then validate it
on the loopback wiring with operator approval. No firmware, bootloader, driver or
raw command is involved.

## Scope

- Offline: payload/frame codec + vectors + validation (done here).
- Live (gated): PWM start/stop for a known frequency/duty, captured back on the
  loopback channel; measure the real period against `period_count`.

## Authority

- May not send PWM to hardware until the operator confirms (a) the device is
  replugged/healthy, (b) the loopback wiring and output logic level, and
  (c) explicit approval. PWM drives pins.
- Never send forbidden opcodes (`0x80/0x82/0x83/0x84/0x85/0x86`). PWM `0x17` is a
  normal user command.
- Do not copy LHX source; the codec here is an independent implementation.

## Acceptance

- Offline vectors pass in CI (no hardware).
- Live: PWM0->CH0 (and PWM1->CH6) capture shows the requested period within one
  sample interval; stop returns the channel to idle; evidence archived and labelled
  `LOCAL_HIL`.

## Handoff template

```text
Task: DL16-TASK-004
State: DONE | BLOCKED | NEEDS_HUMAN_HIL
Offline: <command, counts>
Live: LIVE_NOT_RUN | LOCAL_HIL (per output)
Evidence: artifacts/hil/DL16-TASK-004/ (ignored), SHA256
Risks: wiring/level unconfirmed, device wedge, no independent instrument
Next: <one scope>
```
