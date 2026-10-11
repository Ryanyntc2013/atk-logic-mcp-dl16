# DL16-TASK-066 — offline data correctness and failure safety

Status: **offline fixes complete; gated HIL runner and runbook prepared; HIL_NOT_RUN**.

Branch: `fix/DL16-TASK-066-offline-correctness`
PR: https://github.com/Ryanyntc2013/atk-logic-mcp-dl16/pull/1

## Changes

1. `logic_filter` exclusively creates a new capture directory. It **never** overwrites an existing capture, even when the compatibility parameter `overwrite=True` is passed. Original file content and original `meta.json` remain unchanged; derived metadata is written last.
2. Filtered captures separate software `processing_status` from source acquisition `capture_complete_received`, `trigger_ack_received`, `data_integrity`; record `source_sha256`, `source_integrity`, original source and transform. The derived artifact must never be promoted from `UNVERIFIED` to `COMPLETE`.
3. For ordinary Buffer source captures, preserve untouched peer channels and their common sample clock; fail if peer data are missing or misaligned.
4. UART decoder skips candidate falling edges inside an already consumed frame. A real byte with a valid stop is consumed even when parity fails, so data-bit edges are not decoded as extra bytes. A failed stop is not stored, does not use the result limit, and the search resumes one bit later only after a full bit of idle-high. A noise false start cannot hide a later byte. Back-to-back valid bytes must not spawn extra valid frames.
5. Reject duplicate-channel trigger conditions and explicit host timeouts that cannot encompass trigger wait, acquisition duration and a minimum cleanup margin. An omitted `trigger_timeout_sec` still counts as the device default of 30 s, including when `timeout_s` is explicit. When `timeout_s` is omitted, the host deadline expands from the 45 s default so a documented 1..3600 s trigger wait still fits.
6. Stream offline loader supports explicit per-channel `valid_samples` in `stream_meta.json` and marks byte-count-inferred sample depth as unverified; do not claim calibrated timing.
7. Self-test requires `safety_confirmation="CONFIRMED_SAFE_WIRING_GUI_CLOSED"` (breaking rename of `confirm_safe_wiring`), `DL16_BACKEND_MODE=session`, and an atomic device claim. The claim and the busy check are one critical section: a second self-test or another thread's session open sees the device as busy before PWM starts. `device_busy()` is also true for an open session, a retiring owner, or an in-flight buffer/stream. Closing a session clears the operation id once the child is confirmed gone, including after a cancel timeout, so a retired owner does not stay busy until process restart. A kill that does not reap the child keeps the id. Oneshot mode returns `SESSION_MODE_REQUIRED` and does not drive PWM. A close result of `{success: true, closed: false}` means no session was open and is clean; a failed close is not. A stream start that returns an operation id is cancelled even when `success` is false. Every exit path runs bounded cleanup. `cleanup_ok=False` blocks positive verdicts. A successful loopback diagnostic is `DIAGNOSTIC_PASS_UNCALIBRATED`, not a calibration certificate.
8. Glitch filtering no longer expands full captures into a sample-per-byte array. It uses bounded/chunked edge extraction and packed-byte range edits, preserving sample counts.

## Offline tests

`tests/test_task066_offline_safety.py` covers:

- original and other existing capture immutability, including overwrite requests
- preserve unmodified peer channels; refuse short or misaligned peer data
- SHA-256/source-integrity preservation and no synthetic acquisition claims
- consecutive UART framing (0x6B DE F6 49)
- duplicate AND channel and host/device timeout mismatch
- Stream valid-bit-count authority
- already-owned session rejection and PWM-failure cleanup
- failed cancellation or cleanup cannot return healthy
- differential packed glitch filtering against the original bitwise reference over edge cases
- nominal **mocked** self-test results remain explicitly uncalibrated

Run:
```powershell
python -m pytest -q
python -m compileall -q src
```

## Remaining hardware gate (NOT attempted by this PR)

Under operator-confirmed PWM0->CH8 / PWM1->CH14 loopback, GUI closed:

- normal self-test and output-off check using an independent readout
- PWM1 configure failure injection after PWM0 is already active
- active Stream poll timeout / lost response / cancel failure
- physically check PWM stops, USB is released and a fresh status is possible
- preserve logs/artifacts and hashes, report uncertainty rather than promoting an unverifiable result

Never run automatic HIL for this task from CI. Raw/RLE/absolute timing calibration remain out of scope.

## Deployment policy

PR stays draft until offline CI passes, review is complete, and local hardware gate is either performed or explicitly deferred. Main remains unchanged during this offline work.
Self-test cleanup semantics: `cleanup_ok` means **software commands/owned worker closure confirmed**, while `physical_pwm_off_verified=False` explicitly requires later instrument observation. A final close response must confirm `closed=True` if output could have been active.

## Prepared on-site validation

One-case-at-a-time gated runner: `scripts/dl16_task066_hil.py`.
Hardware runbook: [DL16-TASK-066-hil-validation.md](DL16-TASK-066-hil-validation.md).
Safety checks for harness dry-run: `tests/test_task066_hil_harness.py`.
This remains **NEEDS_HUMAN_HIL**: real PWM-off and USB owner release require physical observation. No automatic CI HIL.
