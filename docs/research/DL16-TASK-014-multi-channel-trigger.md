# DL16-TASK-014 — multi-channel trigger conditions

**Date:** 2026-10-10
**Evidence tier:** LOCAL_HIL on the owner's DL16 Plus (MCU v1.9, FPGA v2.22).
**Change:** tracked patch to the ignored CLI `parse_trigger` — accepts a comma-separated
`chN:kind[,chM:kind...]` list (all conditions AND'ed), matching LHX `--trigger-states`.
`config.CaptureRequest.validate` accepts the list.

## HIL results (PWM0 -> CH8 1 kHz, PWM1 -> CH14 2 kHz, 20 MHz/20 ms)

| Trigger | Completed |
|---|---|
| `ch8:rising` | yes |
| `ch14:high` | yes |
| `ch14:rising` | yes |
| `ch8:high,ch14:high` (AND) | **yes** |
| `ch8:falling,ch14:high` (AND) | **yes** |
| `ch8:rising,ch14:high` (AND) | no (timeout) |
| `ch8:rising,ch14:low` (AND) | no (timeout) |
| `ch8:rising,ch14:rising` (AND) | no (timeout) |
| `ch0:rising,ch8:rising` (CH0 dead) | no (timeout) — correct AND gating |

## Conclusion

- Multi-channel **AND** triggering is functional: two simultaneous conditions
  complete (`ch8:high,ch14:high`, `ch8:falling,ch14:high`), and an unsatisfiable
  AND (`ch0:rising` on a dead channel) correctly waits/timeouts.
- `ch8:rising,ch14:*` failing while `ch8:falling,ch14:high` succeeds is consistent
  with the **fixed relative phase** of the two independently-started PWMs (CH8's
  rising sample does not coincide with a CH14 level on this setup), not a proven
  device limitation. Certifying edge+level coincidence needs a controlled
  overlapping source (out of scope here).
- No absolute timing / uncertainty claim is made.

## Reproduce

```powershell
.\tests\native\build\Release\dl16-pwm.exe start 0 1000 50   # CH8
.\tests\native\build\Release\dl16-pwm.exe start 1 2000 50   # CH14
# logic_capture([8,14], trigger="ch8:high,ch14:high")  -> success
# logic_capture([0,8], trigger="ch0:rising,ch8:rising") -> gated timeout
```
