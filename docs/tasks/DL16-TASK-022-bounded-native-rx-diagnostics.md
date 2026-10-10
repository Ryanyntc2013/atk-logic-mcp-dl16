# DL16-TASK-022 — bounded native receive diagnostics

## Objective and authorization boundary

Baseline `5c24dee8467af60fbf12cdd6436e2666ea3e1e71`. TASK-021 proved the corrected channel configuration did not remove second-request zero samples; a separate postflight info failed with a zero 512-byte MCU header. Neither observation establishes the root cause. Current device readiness is unknown.

The operator authorized autonomous hardware progression with onsite CH8/CH14 safety confirmation. This implementation phase is nevertheless offline: add bounded observations without altering device behavior. No automatic USB reset, endpoint clearing, power cycle, firmware/driver operation, arbitrary vendor command, or capture replay is part of this task. Existing operator LOCAL-HANDOFF modification remains excluded.

## Plan

Add versioned optional bounded native diagnostics: read-size aggregates, parsed message counts/order sequence, channel bytes/samples before and after crop, ACK/Complete positions and trigger offsets where observable. Include diagnostics for incomplete results rather than converting them into successes. No waveform-sized tool messages. Keep raw read, parser and crop authority separate. Do not change receive termination, draining, delays, stop/sleep or FPGA sequencing.

Retain reproducible changes in tracked native patches, apply against a fresh pinned clone, compile and validate independent offline diagnostic aggregation vectors. Avoid running the upstream hardware-open test suite as offline validation. Preserve source pins and LHX unresolved-license restrictions; independently implement observations.

## Acceptance and evidence

- Boundedness and aggregation tested using offline vectors.
- Normal and incomplete result JSON expose requested diagnostics with explicit schema/version.
- Fresh pin plus ordered tracked patches builds without leftover ignored headers.
- Existing Python regression tests and compileall pass.
- Before any new physical block, establish readiness with a separately recorded status; stop if it fails, without automatic reset or broad retry.
- A later bounded two-request diagnostic block is a new experiment, not replay of TASK-021; preserve both failed and successful records.

## Implemented and verified — 2026-10-11

Optional environment switch `DL16_NATIVE_DIAGNOSTICS=1` enables aggregate read counts/bytes, short reads, unaligned byte counts, total message/order counts, first 32 message orders and requested-channel samples before/after crop with crop offsets. Result JSON includes versioned `dl16-rx-diagnostics/v1` on both success and failure. Disabled mode only reports `enabled:false`. No capture sequencing, stop, drain, termination or retry behavior changed. First-order history is bounded; this is not raw RX retention, stale-message proof or a full transport-error timeline. Pre/post-crop fields are absent if execution never reaches that stage.

Tracked diagnostics patch applies after base and session patches. Both an isolated pinned clone build and a second fresh pinned clone with all three patches built with VS2022/v142, exit 0. Original operational binary was not replaced. No upstream test executable was run (it includes hardware-open tests).

Strictly offline seam: `tests/native/diagnostics_test.cpp`, compiled with VS2022/v142 `/std:c++17 /MT /EHsc` against isolated `atkdl16_core.lib`, ran successfully (exit 0). It checks disabled counters, read aggregation, 32-entry sequence cap, 100 order observations, crop counters and failure/success JSON serialization. The seam is also wired into existing native CMake/CI; remote CI has not run.

Python: `.venv\Scripts\python.exe -m pytest -q` — **134 passed in 5.30s**. `.venv\Scripts\python.exe -m compileall -q src` passed. Fresh native configure/build and offline seam are local evidence, not HIL acceptance.

Authorized readiness probe with the fresh diagnostic CLI failed again: `Invalid MCU version header`, 512-byte zero preview. Recorded in `artifacts/hil/DL16-TASK-022/readiness.txt`. No retry, reset or capture followed. Consequently diagnostic capture **HIL_NOT_RUN**; device readiness is **BLOCKED**.

One-shot remains default; B6 mitigation retained. Evidence location: ignored `artifacts/hil/DL16-TASK-022/`. No remote push. Temporary isolated checkouts/builds are not runtime replacements or tracked upstream changes.

Next: establish device readiness with an explicitly scoped operator recovery action before any more capture tests; do not interpret the header error as proof firmware is damaged. Then run a new bounded diagnostic two-request block. The overall stable-session goal remains unfulfilled until that HIL gate and repeatability pass.
