# DL16 PWM output configuration (research + offline codec)

**Date:** 2026-10-10
**Status:** OFFLINE_CODEC (implemented) / LIVE_NOT_RUN (no PWM sent to hardware yet).
**Task:** DL16-TASK-004 (extends DL16-TASK-002 protocol work).
**Provenance:** LHX369963/dl16-cli@8d7c209 `docs/protocol/pwm.md` (behavior + author
live tests = REPORTED_HIL, not our device), the original ATK-Logic app transaction,
and an independent reimplementation. No LHX source was copied (no license located).

## Command

PWM output uses `Command 0x17` through the **same** device frame path as other
commands (`build_device_frame`): `8x00 + 0x0A + (cmd 0x17, len) + payload + 0x0B +
LE CRC32`, zero-padded to 2048 B and 4-lane interleaved.

The pinned CPP backend only defines the `PWM = 0x17` constant and exposes **no**
builder or CLI subcommand; the codec below fills that gap.

## Start payload (9 bytes)

```text
byte 0   : (channel << 4) + 0x11
bytes 1-4: period_count, uint32 little-endian
bytes 5-8: duty_count,   uint32 little-endian

period_count = floor(200_000_000 / frequency_hz + 0.5)   # 200 MHz counter clock
duty_count   = floor(period_count * duty_percent / 100 + 0.5)
```

Reference vector (documented 1 kHz / 50 % original-app transaction):
`channel 0 -> 11 40 0d 03 00 a0 86 01 00` (`200000`, `100000`).

## Stop payload (1 byte)

```text
byte 0: (channel + 1) << 4        # channel 0 -> 0x10, channel 1 -> 0x20
```

## Configuration limits

| Item | Value | Source |
|---|---|---|
| PWM outputs | 2 (channels 0, 1) | DL16 UI; LHX CLI rejects channel > 1 |
| Counter clock | 200 MHz | original-app transaction; LHX |
| Frequency range | 1 Hz .. 20,000,000 Hz | LHX CLI validation |
| Duty range | 0 .. 100 % | derived |
| Rounding | half-up (`+0.5`, floor) | matched to original disassembly per LHX |

## Offline implementation (this repository)

`tests/protocol_reference.py`:
`pwm_start_payload`, `pwm_stop_payload`, `pwm_period_count`, `pwm_duty_count`,
`pwm_start_frame`, `pwm_stop_frame`, plus channel/frequency/duty validation.
Vectors/tests: `tests/test_protocol_vectors.py` (payload bytes, ch0/ch1, stop,
frame wrapping under cmd `0x17`, half-up rounding, invalid-input rejection) and
the golden artifact `tests/vectors/dl16_protocol_vectors.json`.

## Gated live plan (NOT executed)

PWM output drives physical pins; `AGENTS.md` requires operator-approved wiring.

1. Replug the DL16 (it is currently wedged after the 16-channel attempt; live
   captures time out until physical replug).
2. Operator confirms the loopback wiring per output (PWM0 -> CH0, PWM1 -> CH6) and
   the output logic level.
3. Send PWM start for a known frequency/duty, capture the loopback channel, and
   confirm the measured period equals `period_count` counter ticks at the selected
   sample rate (e.g. 1 kHz at 20 MHz -> 20000 samples/period).
4. Send PWM stop; confirm the channel returns to idle.
5. Record evidence under `artifacts/hil/DL16-TASK-004/` (ignored) and label the
   result `LOCAL_HIL`; a successful software frame build is not a hardware result.

Until then, PWM remains `LIVE_NOT_RUN` / `HIL_NOT_RUN`.
