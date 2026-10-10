# DL16-TASK-002 gate B3 — local trigger-gating observation

**Date:** 2026-10-10
**Evidence tier:** LOCAL_HIL observation on the owner's DL16 Plus (MCU v1.9,
FPGA v2.22, USB 2.0). Full evidence (ignored):
`artifacts/hil/DL16-TASK-002/FINDINGS-B3.md` + `b3-gating.json`.

## Setup

PWM0 -> CH0 loopback (operator-confirmed). CH0, 20 MHz, 1.6 V, trigger position
10 %. Payload is the pinned CPP **9-byte** SimpleTrigger (`ch0:rising`,
`is_instantly = 0`).

## Observation

| Scenario | Trigger | Completed | Elapsed | CH0 edges |
|---|---|---|---:|---:|
| PWM on | immediate | yes | ~0.3 s | 20 |
| PWM on | `ch0:rising` | yes | ~0.3 s | 20 |
| PWM off | immediate | yes | ~0.3 s | 0 |
| PWM off, no edges | `ch0:rising` | **yes** | **0.34–2.5 s** | 0 |

An edge trigger with **no signal edge present** completed promptly instead of
waiting, i.e. simple-trigger edge gating was **not observed**.

## Interpretation

- Reproduces HUGEL's report (constant-level capture completed despite an edge
  request); contradicts LHX's edge-gating REPORTED_HIL.
- Order-4 ACK plus a non-zero order-3 offset are **not** proof of real gating.
- Possible cause: this firmware may require the 10-byte trigger payload variant
  (LHX/HUGEL) rather than the pinned 9-byte payload. **Not changed.**

## Status

- B3: `LOCAL_HIL observation` / gating `UNVERIFIED` (not observed).
- No live trigger encoding was modified.
- Follow-up (operator-approved): compare 9B vs 10B gating on the same loopback.

## Cross-references

- Research: `docs/research/LHX369963-dl16-cli-cross-validation-2026-10-10.md` (R2).
- PWM loopback tool: `docs/research/DL16-TASK-002-pwm-output.md` (DL16-TASK-004).
