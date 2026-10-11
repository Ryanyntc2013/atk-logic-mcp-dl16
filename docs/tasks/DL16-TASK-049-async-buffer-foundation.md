# DL16-TASK-049 — genuine asynchronous BUFFER foundation

State: **NEEDS_HUMAN_HIL / Stream remainder BLOCKED**. Initial implementation and cancellation-code followup: HIL_NOT_RUN by child; parent physical cancellation observed below. No USB access by child, no commit. Base 69ffb2421f00d313636c3b7f58b9f7dfd23d587f.

## Objective / scope / design

Deliver actual cancellable native work, not TASK-036's advertised-but-unimplemented Stream. Pinned CPP has Stream parameter/mode support but CaptureEngine accumulates a SampleStore until completion, and mode-specific stream tails/backpressure/incremental artifact semantics remain unresolved. This delivery explicitly does NOT advertise Stream, deliver incremental sample streaming, or certify Stream tails.

Tracked final bootstrap patch `scripts/patches/atk-dl16-async-buffer.patch` plus independently authored `scripts/async_dispatcher.h` implement a main input/control thread and single Device owner thread. Only the owner constructs, opens, uses and closes Device. Input cancel merely sets an atomic flag; owner observes it between bounded 200ms receive calls and sends existing Stop, serialized with all USB control. No reset/recovery/vendor/firmware/driver operations added. Device open/handshake and artifact flush/save can exceed that receive bound; no physical cancellation-latency guarantee.

`hello` advertises `async_buffer_v1`, NOT Stream. `capture_start` acknowledges immediately with request ID as operation ID; `capture_poll` returns running/finished and a bounded nested response; `capture_cancel` requests cooperative cancellation. Only one operation/result retained; control requests while running return SESSION_BUSY; wrong ID fails closed. EOF sets cancellation and joins owner; host close cancels/polls for <=3s before graceful close, falling back to existing owned-child termination with explicit failure. Existing one-shot and synchronous capture use no external cancellation pointer and retain their behavior. Legacy workers are capability-gated before new commands are sent.

Hard async policy: <=2 channels, <=20MHz, <=30s, immediate trigger only, no RLE or caller mode override, <=200MiB retained packed bytes. Unrequested channel packets are discarded for async work. Async edges are omitted to prevent edge-list amplification; sample bytes remain on disk. BUFFER completion retains existing crop/ACK/depth semantics, not a new Stream-tail implementation. Async partial/error/timeout artifacts are saved uncropped with INCOMPLETE, `partial_uncropped=true`, `edges_omitted=true`; Python loading rejects these before waveform analysis. Native source REAL_HARDWARE remains only a source declaration. No sample journal/incremental artifact persistence is claimed; forced process death can lose in-memory samples. Disk saves may be slow; exact final retained-byte cap excludes metadata/raw RX/temporary allocation overhead.

## Public API / parent-only HIL invocation

Use repository MCP instance only, `DL16_BACKEND_MODE=session` and current rebuilt `DL16_CLI_PATH`. Existing approved depth lifecycle may remain `DL16_EXPERIMENTAL_SESSION_LIFECYCLE=depth-stop-v1`. Parent must ensure no competing owner/GUI. Use existing confirmed wiring/threshold, not this document as new wiring authorization:

1. `logic_buffer_start(channels=[8,14], sample_rate_hz=20000000, duration_ms=10, threshold_voltage=1.6, trigger_timeout_sec=30)`.
2. Poll `logic_buffer_poll(operation_id=<returned ID>)` until finished; verify nested result COMPLETE, ACK/Complete, exact counts and stop fields. Analyze saved capture with existing PWM tools; no calibration claim.
3. For cancellation gate only after parent approves the longer capture: start same channels/rate/threshold with `duration_ms=1000`, immediately call `logic_buffer_cancel(operation_id=<ID>)`, poll until finished. A race completing before cancellation is NOT cancellation acceptance. Retain request/reply timestamps, partial metadata/hash, stop fields, worker PID, cleanup result. Cancellation partials must remain INCOMPLETE and fail analysis loading.
4. `logic_session_close()`; retain exit/cleanup evidence. Never launch a second one-shot/native owner alongside this session.

Equivalent native JSONL commands: `capture_start`, `capture_poll`, `capture_cancel` with protocol-1 hello and correlated request_id; capture_start includes channels/sample_rate_hz/duration_ms/threshold_voltage/output_dir. Poll/cancel require operation_id. No physical test performed by this child.

## Acceptance / exact commands and results

- `powershell -File scripts\bootstrap-native.ps1 -SkipTests`: full patch stack configure/build exit 0. Upstream hardware-open tests intentionally not executed.
- `cmake -S tests\native -B tests\native\build` then `cmake --build tests\native\build --config Release --target dl16-async-buffer-test --parallel`: actual production dispatcher USB-free harness built, exit 0.
- `.venv\Scripts\python.exe -m pytest -q tests\test_async_buffer.py`: 15 passed. Covers native owner cancellation <1s, busy/wrong-ID controls, EOF join, active close, actual patched worker invalid requests without Device open, native partial artifact bytes/metadata/write failure and Python fail-closed loading.
- `.venv\Scripts\python.exe -m pytest -q`: 250 passed in 7.72s on final rebuilt patch stack.
- `.venv\Scripts\python.exe -m compileall -q src`: exit 0.
- Ruff new test module passes; affected existing modules have pre-existing import/TRY004/observer lint findings, not silently fixed. CI selector includes actual async tests; no remote CI claim.

Ignored build/test logs: artifacts\task049-build.txt, task049-harness.txt, task049-pytest.txt. Native synthetic harness never constructs Device. Native live cancellation/timeout/artifact paths are source-built but not USB-mocked at transport level; their physical correctness remains HIL_REQUIRED. Next task: bounded parent cancellation HIL, then separately design validated Stream tails and incremental writer/backpressure; do not widen capability based on BUFFER success.

Initial native binary SHA256: BFBAE49FA3B89D4274F664CFAADF09A1B791438311ABD57F2AD861B5D9404EE0. Diff check exit 0 (Windows line-ending warning only).

## Narrow cancellation-code followup (2026-10-11)

Parent physical record `artifacts/hil/DL16-TASK-049/requests.json` (SHA256 `1A988FFD08DCFAFFE75D68459133ED5605D4CC8BD76EB3EF577B154C8CD06244`) is preserved unchanged. For operation `p11496-2`, CH8/CH14, 20MHz, requested 1000ms, cancellation finished with `success=false`, `data_integrity=INCOMPLETE`, `capture_complete_received=false`, cancellation message and `cleanup_stop_attempted=true`, `cleanup_stop_ok=true`. Parent reports atomic handling/stop gate passed; record nevertheless exposed misleading `error_code=OK`. These are parent physical observations on the pre-fix binary, not a child HIL run or true Stream validation.

The tracked async patch now routes stopped async capture to existing `ErrorCode::IncompleteCapture` / `INCOMPLETE_CAPTURE`. A shared native classification seam is used by the actual CaptureEngine branch and USB-free synthetic harness. Legacy synchronous stop remains `OK`; both timeout classifications remain `CAPTURE_TIMEOUT`. Artifact-write failures still override with their actual non-success error. Regression invokes the real native serializer and asserts false success, INCOMPLETE integrity, INCOMPLETE_CAPTURE code and cancellation message; native assertions cover synchronous compatibility and timeouts. No Device is constructed for this test.

Exact followup validation:
- `powershell -File scripts\bootstrap-native.ps1 -SkipTests`: exit 0; no upstream hardware tests executed.
- `cmake -S tests\native -B tests\native\build` and `cmake --build tests\native\build --config Release --target dl16-async-buffer-test --parallel`: exit 0.
- `.venv\Scripts\python.exe -m pytest -q tests\test_async_buffer.py`: **16 passed in 0.48s**.
- `.venv\Scripts\python.exe -m pytest -q`: **251 passed in 7.83s**.
- `.venv\Scripts\python.exe -m compileall -q src`: exit 0.
- `git diff --check`: exit 0 (existing Windows line-ending warning only).

Build logs are separate `artifacts/task049-cancel-fix-build.txt` and `artifacts/task049-cancel-fix-harness.txt`; original parent HIL artifacts were not rewritten. Rebuilt binary SHA256: `21EBE63379AD223DEB315DE6CAFA09E08F7329B330A642A118071D975B0A2642`. Commit: none by request. Followup status: DONE offline; HIL_NOT_RUN on corrected binary. Next: parent-only bounded corrected-code cancellation verification, then separately gated Stream tails/incremental persistence/backpressure.

Parent corrected-binary HIL: one approved 1000ms CH8/CH14 async request immediately cancelled; bounded poll finished with success=false, INCOMPLETE_CAPTURE, INCOMPLETE and both cleanup_stop fields true. Session close returned. Evidence artifacts/hil/DL16-TASK-049/corrected/records.json, journal, partial artifacts and close.json. Original misleading-OK run retained. This validates this single cancellation path, not latency under open/save failure or true Stream.
