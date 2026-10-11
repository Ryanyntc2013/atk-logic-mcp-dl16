# DL16-TASK-043 — Offline persistent-session reliability

## Objective and permitted scope

Extend persistent owner and mixed-worker-generation contracts using deterministic
fake subprocess workers. Change only `src/dl16_mcp/session.py`, focused session
tests, and directly related documentation. No USB, loaded MCP tools, PWM output,
firmware, hardware operations, or edits to the pending raw-RX/RLE files. No commit
requested or made. Evidence tier: **CONTRACT_MOCK / OFFLINE**; **HIL_NOT_RUN**.

## Plan and coverage review

Read `AGENTS.md`, `docs/LOCAL-HANDOFF.md`, and `docs/SOURCES.md` first. Reviewed
existing session, journal, smoke and public PWM tests. Existing coverage already
checks reuse, concurrent serialization, generic mismatched IDs, malformed JSON,
child exit, real fake-subprocess timeout, idempotent close, journal errors and
cleanup failures. Added complementary contracts, rather than another generic
successful capture or malformed-response test:

- Reject missing, unsupported, boolean and string hello protocol versions before
  any requested operation; failed owners cannot silently launch another worker.
- Keep capability advertisements owner-local across legacy/current workers;
  closing one child must not stop another. Legacy protocol-1 hello without a
  commands list retains status compatibility but cannot send PWM requests.
- Deterministic response expiry escalates terminate/wait to kill/wait on only the
  failed child, closes its pipes, and does not replay capture on an explicitly
  created fresh owner or send a close command to the failed owner.
- A delayed valid response from the previous request is not accepted as the new
  capture result; mismatch diagnostics retain both request IDs. Fresh owners use
  independent queues and must complete hello before status.
- Broken stdin writes invalidate ownership without replay; local oversized
  requests are rejected before transmission without poisoning a healthy owner.

The new Popen-shaped workers synchronously inject scripted JSONL at flush. Their
queue timeout and terminate/kill waits are simulated without sleeping, starting
real subprocesses, launching reader threads, or unbounded loops. The pre-existing
focused tests still exercise actual Python child pipes and reader threads.

## Bug and fix

The five incompatible-hello regressions initially failed: `_start()` accepted
any successful hello response regardless of its `protocol` field and sent the
caller operation. Added strict integer protocol-1 validation before assigning
capabilities or accepting hello. Missing/malformed/incompatible versions now
raise `SESSION_PROTOCOL_ERROR`, invalidate and stop only that owned child, and
never send the caller operation. A protocol-1 worker without `commands` remains
compatible for non-PWM operations. No live/native protocol implementation changed.

## Exact validation and results

All commands ran from `E:\code\atk-logic-mcp-dl16` using the checkout interpreter.
Pytest scratch files were directed into the ignored repository artifact tree.

Initial test-harness run exposed recursion in its queue monkeypatch; corrected
that fixture before assessing production behavior. The subsequent baseline:

```powershell
.venv\Scripts\python.exe -m pytest -q tests\test_session_reliability.py --basetemp=artifacts\pytest-task043 --tb=short
```

Result before the production fix: **5 failed, 6 passed in 0.18s**, all five failures
were the incompatible hello cases (`DID NOT RAISE SessionFailure`).

Final focused validation:

```powershell
.venv\Scripts\python.exe -m pytest -q tests\test_session.py tests\test_session_reliability.py tests\test_session_journal.py tests\test_session_smoke.py tests\test_public_pwm.py --basetemp=artifacts\pytest-task043
.venv\Scripts\python.exe -m compileall -q src
```

Results: **60 passed in 11.33s**, exit 0; after adding an explicit timeout pipe-closure assertion, the same focused command returned **60 passed in 11.06s**, exit 0. Compileall emitted no output, exit 0 on both runs.
Editor diagnostics reported no errors in either changed Python file. Repository-wide `git diff --check` found only pre-existing trailing blank lines in the excluded `tests/native/CMakeLists.txt` and `tests/test_config.py`; these were left untouched. Task-scoped diff checking passed.

## Provenance, limitations and handoff

Tests and fix independently derive from this repository's host-side owner and
JSONL contracts. No external implementation was consulted/copied; existing
upstream pins and authority distinctions in `docs/SOURCES.md` remain unchanged.

**DONE** (offline bounded deliverable). Commit: **none**, as requested. Existing
raw-RX/RLE worktree changes were preserved. No full-suite, native executable or
hardware acceptance claim. Scripted failures verify host ownership/correlation,
not OS scheduling, pipe teardown races, firmware gating or physical acquisition
generation identity. Native command errors retain existing policy; this task
changes only hello version rejection, not capture-failure handling in backend.
Next suggestion: separately authorize remaining raw-RX/RLE offline gates; obtain
new explicit operator authorization before any physical session reliability HIL.
