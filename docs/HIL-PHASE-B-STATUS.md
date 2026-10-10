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

## DL16-TASK-016 (B-1 phase diagnosis, B-2 gating repeatability)

- B-1 (2 channels, no trigger, PWM0 100 Hz + PWM1 1000 Hz, both 50%): raw bits show CH8 rising edges
  at samples 200000/400000/600000/800000 and CH14 LOW at all four. The two frequencies are
  harmonically related, so the phase is fixed. ch8=rising AND ch14=high has 0 matches in the
  data; ch8=high AND ch14=high has 250000 and ch8=rising AND ch14=low has 4. The search and
  device AND behave correctly; the earlier ch8:rising,ch14:* timeouts were a phase artifact,
  not a device fault. Non-harmonic frequencies are still needed to observe a true edge+level overlap.
- B-2 (ch0:rising, no signal, --trigger-timeout 3, 20 runs): 20/20 CAPTURE_TIMEOUT,
  elapsed 3.60-3.63 s; device ready before and after.
- Evidence: rtifacts/hil/DL16-TASK-016/ (ignored) with SHA256SUMS.txt. B-2 per-run values are
  transcribed from the console output, not from a saved file.

## DL16-TASK-017 (B-1b, non-harmonic multi-channel AND)

- PWM0 100 Hz and PWM1 1007 Hz (both 50%), CH8+CH14, no trigger, 50 ms, complete (1,000,000 samples/channel).
- Search on the raw capture: `ch8=rising AND ch14=high` 3, `ch8=rising AND ch14=low` 2, `ch8=falling AND ch14=high` 4.
  A raw bit check agrees (3 of 5 CH8 rising edges have CH14 high). A real edge+level overlap now exists.
- Device gating: `--trigger "ch8:rising,ch14:high" --trigger-timeout 3` returned `success=true`,
  `COMPLETE`, `trigger_ack=true`. The first matching sample is 100000 (10% of total, the default
  pre-trigger position). The result JSON does not expose the trigger offset, so this is inferred from the sample index.
- Conclusion: the multi-channel AND trigger works on hardware for an edge+level condition with
  non-harmonic PWM. The earlier 100 Hz/1 kHz timeouts were a phase artifact.
- Evidence: `artifacts/hil/DL16-TASK-017/` (ignored) with SHA256SUMS.txt. PWM outputs were stopped; device ready after.

## DL16-TASK-018-C (persistent-session comparison; acceptance FAILED)

TASK-019 correction: session requests for CH8/CH14 accidentally retained default
CH0/CH1; archived metadata shows four configured channels. The one-shot comparison
configured only CH8/CH14, so identical-configuration conclusions are withdrawn.
The parser and patch packaging have been repaired with a real parser regression
and a fresh-clone build; no new capture HIL was performed. The zero-sample failure
remains observed, its physical cause unresolved, and session remains unaccepted.

- Wiring: PWM0->CH8, PWM1->CH14; 100 Hz and 1007 Hz, 50% duty. Capture: CH8+CH14,
  20 MHz, 10 ms (200,000 samples/channel), immediate trigger. GUI was not running.
- Ownership probe: a second session received `DEVICE_OPEN_FAILED` with port-claimed text;
  it closed without disturbing the owner.
- Initial session response framing defect was fixed offline (nested multiline capture JSON
  must be compacted before embedding). First session capture artifact was written, but its
  parent call failed with `SESSION_PROTOCOL_ERROR`; it is retained as a failed protocol attempt.
- After the fix, session run 1 completed. Session run 2 returned `INCOMPLETE_CAPTURE` with
  Complete present but all enabled channels 0/200,000. The block stopped immediately, no
  retry/replay; persistent-session acceptance FAILED.
- One-shot comparison: 20/20 COMPLETE, 200,000 samples on CH8 and CH14. 16/20 used the
  bounded B6 retry (first open-after-capture FPGA device-info parse failure), 4/20 succeeded
  on attempt 1. All artifacts passed metadata checks. Final device status connected/ready.
- Evidence: `artifacts/hil/DL16-TASK-018/` with 435-file SHA256 manifest. PWM outputs stopped.
- Operational decision: keep one-shot as default and retain B6 retry. Do not use session mode
  for captures until the zero-sample Complete path is reproduced and fixed offline, then
  separately revalidated in a newly approved HIL block.

## DL16-TASK-021 — corrected-channel session smoke (FAILED)

After renewed operator connection/wiring/safety confirmation, a single persistent native PID processed two CH8/CH14 requests at 20 MHz, 10 ms, 1.6 V, immediate trigger. First capture: metadata exactly `[8,14]`, COMPLETE, ACK/Complete and 200,000 samples/channel. Second capture: Complete present but 0/200,000 on both requested channels, `INCOMPLETE_CAPTURE`. The block stopped without replay, fallback or third capture; session closed. PWM was not configured and waveform quality was not evaluated.

A separate postflight `info` failed with `Invalid MCU version header` and a 512-byte zero preview; readiness is not confirmed after the block. No reset or recovery change was attempted. This does not establish firmware damage or identify the zero-sample cause.

Evidence now includes full durable request/response JSONL and per-step records under ignored `artifacts/hil/DL16-TASK-021/`, not raw USB RX. See [TASK-021 report](tasks/DL16-TASK-021-corrected-session-smoke.md). Keep one-shot default and B6 retry; next gate is bounded native receive diagnostics, not a repeatability block.

## DL16-TASK-023 — restored-device receive diagnostics (FAILED)

Operator restored the device; fresh readiness passed. With TASK-022 diagnostic CLI, first corrected CH8/CH14 capture passed. Second received exactly one aligned 16,384-byte read, message orders `[6,6,6,4,5,5,5,5]`, no channel-data messages, zero samples before and after crop. Stop-on-failure worked; no third request or reset. This rules out crop clearing for this run and prioritizes completion-message ownership/lifecycle investigation, but does not prove the Complete messages came from the prior acquisition. Full report and evidence mapping: [TASK-023](tasks/DL16-TASK-023-session-complete-order-hil.md). Session remains unaccepted; one-shot default and B6 retry retained.

## DL16-TASK-026 — pre-arm flush observations (FAILED)

After operator restoration/readiness pass, both capture requests recorded successful wake writes. Both wake-internal and explicit flushes reached their existing 50-read cap: 102,400 bytes each, no errors, no empty read. First capture passed; second again received `[6,6,6,4,5,5,5,5]` without channel data, zero samples before/after crop. Cap saturation is therefore not sufficient to explain the failure, and flush data content/packet ownership remains unknown. No replay/reset or enlarged drain. See [TASK-026](tasks/DL16-TASK-026-prearm-hil.md). Session remains unaccepted.

## DL16-TASK-028 — experimental depth/stop lifecycle smoke (2/2 capture-valid)

Following operator restoration/readiness pass, opt-in `depth-stop-v1` processed two exact CH8/CH14 requests successfully,200000 samples/channel,required ACK/offset/Complete. Second request still started with three Complete messages before ACK/progress but continued to receive channel data. Session closed and separate postflight info passed. This supports early-Complete termination as a failure mechanism, but grouped wake/flush/completion/stop changes do not establish single-change cause or sample generation provenance. No waveform/source quality check; two captures are not stability certification. Keep one-shot default and session experimental. See [TASK-028](tasks/DL16-TASK-028-experimental-lifecycle-hil.md).

## DL16-TASK-029 — experimental static-input repeatability (20/20)

Opt-in depth-stop-v1 completed20 exact CH8/CH14 requests,200000 samples/channel,required markers; independent pre/post info passed. Elapsed0.125..0.438s. Offline bits inspection found both requested channels entirely low with zero transitions in all20 captures, so this is static-input capture validity/repeatability, NOT PWM waveform or timing validation and cannot rule out mixed generations. Full evidence/report [TASK-029](tasks/DL16-TASK-029-bounded-repeatability.md). Session remains experimental; defaults/B6 unchanged.

## DL16-TASK-030 — known PWM decision gate (overall waveform FAILED)

Reviewed helper started PWM0=1kHz/PWM1=2kHz,50percent;20/20 experimental captures valid. CH14 artifacts all measure2kHz/50percent with20 rising edges/window;CH8 is all-low with no expected1kHz. Both stop helper calls succeeded,postflight info passed. Output command success is not proof of sustained physical PWM0. Overall waveform FAIL;do not promote session. Next decision is isolated PWM setup/output persistence diagnosis versus single-owner session PWM interface. Full report [TASK-030](tasks/DL16-TASK-030-known-pwm-decision.md).

## DL16-TASK-031 — PWM order isolation

PWM0-only produced CH8~1kHz/50percent in both captures. Reverse setup PWM1->PWM0 yielded CH8=1kHz/50percent and CH14 all-low. Combined with TASK030 forward setup yielding only CH14, waveform follows last configured output under sequential standalone helper opens. Both channels' missing-source observations must not be attributed to capture alone. All4 captures valid,outputs stopped,postflight info passed. Next investigate two-output configuration in one ownership interval. See [TASK-031](tasks/DL16-TASK-031-pwm-order-isolation.md);session remains experimental.

## DL16-TASK-032 — scoped long-session buffer acceptance

Same-owner PWM configuration produced simultaneous CH8=1kHz/50percent and CH14=2kHz/50percent in20/20 captures;final stop-observable binary repeated20/20,all stop transfers reported successful. Fresh postflight info passed. No calibrated timing or generation identity claim. Native trigger timeout followed by same-owner immediate request failed,so MCP adapter now closes/invalidates failed capture and does not replay;later explicit fresh-owner capture passed and postflight ready. Close-owned PWM failures surface. This accepts explicit opt-in buffer long-session normal operation with fail-closed error boundary on this Plus firmware baseline,NOT default promotion/stream/RLE/universal trigger/model certification. See [TASK-032](tasks/DL16-TASK-032-single-owner-long-session.md).

## Build patches applied to the ignored checkout (reproducible)

All local native changes are one patch: scripts/patches/atk-dl16-local-build.patch, applied
by scripts/bootstrap-native.ps1 after eset --hard to the pinned commit (DL16-TASK-A1).
It covers: libusb DLL import library (C1900), 10-byte gated SimpleTrigger, --trigger-position,
multi-channel AND, --trigger-timeout. The pinned commit content is never claimed modified.

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
