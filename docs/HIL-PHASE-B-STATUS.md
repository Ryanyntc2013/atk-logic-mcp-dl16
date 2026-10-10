# Phase B / local HIL status (DL16-TASK-001/002/004/010/011)

Device: **DL16 Plus**, USB 2.0, MCU **v1.9**, FPGA **v2.22**, 16 channels.
All results below are **LOCAL_HIL** on the owner's unit unless marked otherwise.
Build: pinned CPP `5fc47744` + two tracked, idempotent build patches (see below).

## Gate scoreboard

| Gate | Result |
|---|---|
| B0 model/handshake | PASS (DL16 Plus, USB 2.0, MCU v1.9, FPGA v2.22) |
| B1 rate indices | PASS: 1/4/5/6/7/8/9/10/11/12/13 MHz verified via PWM loopback; index 7 (25 MHz) and 13 (500 MHz) work here; LHX index-7 no-data / 500M=0 **not reproduced** |
| B2 instant capture | PASS: COMPLETE, exact sample counts |
| B3 edge gating | Initially **not gated** with the 9-byte payload (matches HUGEL) |
| B4 order-3/tails + alignment | Alignment **PASS**: trigger edge at `total × position%`, pre-trigger precedes it (DL16-TASK-013); raw packet byte cross-compare still not done |
| B5 skew | not run (requires split wiring) |
| B6 repeat reliability | 50 % raw (deterministic post-capture open failure) -> **100 %** with bounded backend retry |

## PWM output (DL16-TASK-004)

PWM0->CH0 and PWM1->CH6 verified; matrix 100 Hz..20 MHz exact; duty 50/25/10 %
matched. Command `0x17`, 200 MHz counter, half-up. Tool `dl16-pwm`. (Current wiring:
PWM0->CH8, PWM1->CH14 verified 1 kHz/2 kHz.)

## Trigger gating fix (DL16-TASK-010/011)
- 9-byte SimpleTrigger **does not gate**; 10-byte **does** (edge and level).
- `bootstrap-native.ps1` now applies a tracked patch: non-immediate triggers use the
  10-byte payload; immediate keeps the 9-byte instant flag.
- HIL after the patch (via MCP CLI): CH0 no-edge `ch0:rising` -> `CAPTURE_TIMEOUT`
  (gated); CH8 `ch8:rising` -> success; CH0 `immediate` -> success.

## Trigger position (DL16-TASK-012)

- Tracked patch adds `--trigger-position`; exposed via `logic_capture` /
  `dl16ctl capture --trigger-position`. HIL confirms it reaches the device (order-3
  offset tracks `total - trigger_depth`: pos 10 -> 360007, pos 50 -> 200008 on a
  400000-sample buffer). Returned-buffer pre-trigger **alignment** verified (B4,
  DL16-TASK-013): trigger edge at `total × position%`.

## Multi-channel trigger (DL16-TASK-014)

- Tracked patch accepts `chN:kind[,chM:kind...]` (AND). HIL: `ch8:high,ch14:high` and
  `ch8:falling,ch14:high` complete; `ch0:rising` (dead channel) AND gates/timeouts.
  Edge+level coincidence not certified (fixed PWM phase; needs a controlled overlap).

## Trigger timeout (DL16-TASK-015)

- Tracked patch exposes `--trigger-timeout`; HIL: `ch0:rising` with `--trigger-timeout 3`
  returns `CAPTURE_TIMEOUT` in ~3.7 s (default 30 s).

## Build patches applied to the ignored checkout (tracked, idempotent)

1. libusb DLL import library (older local MSVC vs newer prebuilt static lib; C1900).
2. 10-byte gated SimpleTrigger payload (non-immediate).

Both are applied by `scripts/bootstrap-native.ps1`; the pinned commit content is
never claimed modified. Toolset defaults to installed VS2019 (`v142`) with fallback.

## Reproduced research items

- **R2 resolved:** 9B/10B gating.
- **R1 not reproduced:** CPP rate table correct on this unit.
- **R3 reproduced:** intermittent FPGA device-info parse failure; deterministic once
  after each completed capture; mitigated by backend retry.
- **B3:** order-4 ACK + order-3 offset are not trigger evidence.

## Open / deferred (native or wiring required)

- Persistent JSONL session; Stream capture; hardware RLE; raw wire-packet retention.
- B4 raw packet byte cross-compare (alignment itself verified, DL16-TASK-013).
- B5 common-source skew (requires split wiring).
- sigrok external decoder handoff (optional; VCD export already enables it).
