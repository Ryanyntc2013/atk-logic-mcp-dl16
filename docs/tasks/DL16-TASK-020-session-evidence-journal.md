# DL16-TASK-020 — auditable session evidence journal

## Objective and allowed scope

Add explicitly enabled, local disk evidence for persistent native JSONL requests before corrected-channel HIL. Preserve one-shot as default and the B6 retry. This task implements and validates offline logging only: no USB access, PWM, capture, native bootstrap/test suite, reset, endpoint clearing, firmware/driver changes, or remote push.

Baseline: `53400b28d7eafbcae8d691456f43ca1cd48e85c6`. The existing uncommitted `docs/LOCAL-HANDOFF.md` is operator-provided and is excluded from this task's commit.

## Implementation plan

1. Add an opt-in local session journal with unique files and durable ordered records.
2. Record complete bounded requests before sending, and responses before interpreting errors. Include request IDs, native PID, binary identity, monotonic elapsed time and observed cleanup outcomes.
3. Preserve malformed/timeout/exit evidence and report evidence-write failures explicitly. Never replay a capture or silently switch backends.
4. Keep declared configuration separate from native-reported effective configuration. No raw USB trace or physical authenticity claim is implied by JSONL or file hashes.
5. Add mock-process and disk-I/O regression tests; run Python tests, compileall and diff checks.

## Acceptance and evidence

Offline cases: successful repeated requests; full native error response; malformed JSON; timeout; child exit; journal failure before command dispatch; shutdown; no replay. Existing default behavior must remain compatible.

Commands and final results are recorded below after validation. Offline test logs belong under ignored `artifacts/hil/DL16-TASK-020/`; these are **OFFLINE_TEST / CONTRACT_MOCK**, never REAL_HARDWARE or HIL_PASS.

Native builds are not required because no native patch or protocol behavior is changed. The upstream native suite includes device-open behavior and must not be invoked as an assumed offline test.

## Source provenance and limitations

This feature is independently implemented host-side logging. Runtime remains the pinned native CLI plus tracked patches; see [SOURCES](../SOURCES.md). LHX references remain diagnostic source observations with unresolved licensing, not copied implementation or local HIL proof. Existing TASK-018 console-transcribed records are not retroactively upgraded into complete journals.

## Next physical gate — separate task and renewed authorization

Confirm current device, GUI/USB ownership, safe PWM0 -> CH8 / PWM1 -> CH14 wiring and signal voltage. Begin with one approved CH8/CH14 capture; verify effective metadata channels are exactly `[8,14]` and requested/actual sample counts match. Perform a second request in the same session, stop on first error/incomplete, retain diagnostics, and only then consider a separately bounded repeatability block. Session remains experimental and unaccepted until that gate passes. B5 requires a separately approved common-source split signal.

## Operator usage and record authority

Set `DL16_SESSION_JOURNAL_DIR` to an absolute, local evidence directory before starting the MCP process. This setting does not select session mode; `DL16_BACKEND_MODE=session` is still explicitly required. Leave both unset for ordinary one-shot operation.

Records contain the transmitted requests, bounded raw JSONL responses and parsed results, including native error responses. Requests are caller declarations; returned metadata is native-reported evidence, not independent confirmation of physical wiring. Missing effective channels/sample counts in a response remain unknown; validate retained capture metadata separately before accepting HIL. stderr and USB RX packets are not captured by this journal.

Original journals can contain absolute paths and signal/device metadata. Keep them local; export separately redacted summaries rather than editing originals. Hash the retained evidence with `scripts/hil-evidence.ps1` in its default offline mode after execution. fsync reduces loss from process failure but is not cryptographic authentication or a guarantee against storage/hardware failure.

## Verification

Completed offline acceptance on 2026-10-11:

- `.venv\Scripts\python.exe -m pytest -q`: **122 passed in 4.11s**, exit 0. Output retained in `artifacts/hil/DL16-TASK-020/offline-tests.txt`.
- `.venv\Scripts\python.exe -m compileall -q src`: passed, exit 0.
- `git diff --check`: passed; existing CRLF conversion warnings are not whitespace errors.
- No native bootstrap/test suite or USB operation was run. Physical HIL: **HIL_NOT_RUN**.

Mock regressions cover malformed/non-object/mismatched responses, native errors, timeout/exit without replay, unique files, binary-identity failure boundaries, cleanup uncertainty, journal errors and JSON escape expansion. Records are bounded to 1 MiB to accommodate the raw and parsed copies of a bounded 64 KiB protocol response. Request intent is durable before dispatch; a missing result after a crash remains an ambiguous operation, never authorization to replay.

Delivery status: **DONE (offline scope)**. Corrected-channel session acceptance remains **NEEDS_HUMAN_HIL**. Next task suggestion: `DL16-TASK-021` for separately authorized CH8/CH14 two-request session smoke, followed by a bounded repeatability block only if both requests pass.
