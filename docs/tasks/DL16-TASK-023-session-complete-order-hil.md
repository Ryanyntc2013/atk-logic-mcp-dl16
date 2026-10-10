# DL16-TASK-023 — restored-device diagnostic session observation

## Scope and authority

Baseline `2ef1fde65e24f94027e265a49adbbbd5f64b620e`. Operator reported device restored at 2026-10-11 06:10 +08; previous explicit onsite CH8/CH14 safety and autonomous bounded hardware authorization retained. No PWM configuration, USB reset, endpoint clearing, firmware/driver operation or replay performed.

Readiness with the retained TASK-022 diagnostic CLI passed: Plus, MCU v1.9, FPGA v2.22, USB 2.0. No competing ATK/Logic process observed. Signal waveform remains unverified.

## Experiment

Reuse `scripts/dl16_session_smoke.py` with `DL16_NATIVE_DIAGNOSTICS=1`, explicit retained diagnostic executable path, all live confirmation flags and source declaration. Maximum two requests in one session: exactly CH8/CH14, 20 MHz, 10 ms, 1.6 V, immediate. First failure stops block. This is a new experiment, not automatic replay of TASK-021.

Evidence retained under ignored `artifacts/hil/DL16-TASK-022/evidence/smoke-20261010-221059-00d3611819124f0186a37b37caf9c394/`. The reused harness embeds its historical `task_id=DL16-TASK-021`; preserve originals unchanged and interpret them as harness identity, NOT as reuse of the old experiment. This task report maps the new run to TASK-023 explicitly. Native binary SHA256: `017f12f836cbca455dbf7fdbe9f100a722c69e067d98e1b1f8253317525d6717`.

## Results — LOCAL_HIL / HIL_FAIL

- First request: STEP_SUCCESS, about 0.453 s, 47 reads / 770,048 bytes. Message counts: order1=208, order2=3, order3=1, order4=1, order5=162, order6=1. CH8/CH14 each 200,064 samples before crop/finalize, 200,000 after, crop offsets zero.
- Second request: INCOMPLETE_CAPTURE, about 0.094 s, exactly one read / 16,384 bytes. Eight parsed orders: `[6,6,6,4,5,5,5,5]`. No order1/channel data. Both requested channels zero BEFORE and AFTER crop, offsets zero. No short reads or unaligned bytes recorded in either request.
- Harness returned SECOND_REQUEST_FAILED, exit 1 as intended. No third capture, replay or fallback. Harness reports session close returned successfully; physical readiness after this block was not probed and is unknown.

## Interpretation and limits

This run rules out crop clearing as the immediate explanation for its second-request zero samples: no samples existed before crop. The observed read was aligned and not short; this does not rule out earlier transport/flush effects outside the instrumented receive loop.

Complete messages preceded the new request's ACK/progress in the received sequence. This makes completion-message ownership and acquisition lifecycle the leading investigation direction. It does NOT prove the messages belonged to the prior acquisition: protocol has no recorded capture generation identifier, and this aggregate log does not retain raw USB data, wake/flush telemetry or full timing. Native loop dispatches remaining messages in the current parsed batch even after setting Complete; do not describe it as breaking immediately at the first Complete.

No waveform quality, frequency, trigger gating or calibrated timing pass is claimed. Keep one-shot default and B6 mitigation. No drain/ignore-Complete policy change accepted from this observation alone.

## Verification and next task

Reuse the previously verified bounded harness and diagnostic CLI; no source implementation changed in this experiment. Preserve journal, bundle and step records and update evidence SHA256 manifest offline. Next proposed TASK-024: deterministic offline message-sequence regressions and source comparison for completion ownership, then separately reviewed lifecycle/completion criteria changes. Any experimental policy must distinguish early/stale Complete without silently upgrading incomplete data, be bounded and preserve stop/error evidence. Do not continue live repetitions until such a test-backed plan is accepted.

Outcome: **DONE (diagnostic experiment/report)**; stable-session objective remains **BLOCKED / unaccepted**.
