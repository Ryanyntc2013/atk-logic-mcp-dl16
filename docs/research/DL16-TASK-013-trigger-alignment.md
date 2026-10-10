# DL16-TASK-013 — returned-buffer trigger alignment (B4)

**Date:** 2026-10-10
**Evidence tier:** LOCAL_HIL on the owner's DL16 Plus (MCU v1.9, FPGA v2.22).
**Depends on:** DL16-TASK-011 (10-byte gating), DL16-TASK-012 (trigger position).
**Result: the trigger edge is placed at sample index `total_samples × position%`;
the samples before it are the pre-trigger region. Alignment is correct within one
sample interval.**

## Method

PWM0 -> CH8. Continuous `ch8:rising` gated captures, 20 MHz, 20 ms (400 000 samples).
Trigger position swept. A **100 Hz** PWM (period 200 000 samples) is used so the
trigger index is distinguishable from the edge grid (a 1 kHz grid of 20 000 samples
aliases with the tested positions).

`trig_depth = total_samples × position / 100`.

## Observations (PWM 100 Hz, period 200 000 samples)

| position | trig_depth | order-3 offset | rising edges (sample) |
|---:|---:|---:|---|
| 0 % | 0 | 400003 | 200000 |
| 10 % | 40000 | 360007 | **40000**, 240000 |
| 50 % | 200000 | 200003 | **200000** |
| 90 % | 360000 | 40001 | 160000, **360000** |

The trigger edge (bold) lands exactly on `trig_depth` in every case, and the
pre-trigger region `[0, trig_depth)` contains the preceding edges.

## Conclusion

- With the 10-byte gating payload and `--trigger-position`, the returned buffer is
  aligned so the trigger edge is at `trig_depth`; pre-trigger content precedes it.
- order-3 offset tracks `total - trig_depth`, consistent with the split.
- **Limitation:** alignment is verified to one sample interval; no independent
  instrument; this is device-internal loopback, not an absolute timing certification.
- Raw per-packet/order-3 byte cross-compare (raw `wire`) is still not captured.

## Reproduce

```powershell
.\tests\native\build\Release\dl16-pwm.exe start 0 100 50    # 100 Hz on CH8
# capture ch8:rising with logic_capture(..., trigger_position_percent=pos)
```
