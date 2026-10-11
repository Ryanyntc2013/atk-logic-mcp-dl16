# DL16-TASK-057 — bounded live Stream progress and measured IO elapsed

**DONE offline / NEEDS_HUMAN_HIL; HIL_NOT_RUN.** Base `ab7b9e3`; no commit,
no hardware, no capture, no PWM or wiring change by child. Parent owns hardware.

## Objective / allowed scope / plan

Continue TASK056's parent observation (552704 stored bytes,20MHz/100ms,
DEADLINE, ACK observed, no Order6, Stop/close successful), without treating it as
sustained throughput or COMPLETE. Publish actual stored-byte/read progress during
production Stream receive, permit deterministic cancel-after-data, measure IO
elapsed, preserve receive deadline and per-chunk flush. Rebuild tracked native
patch/bootstrap/header stack; exercise actual dispatcher/parser/writer with
USB-free injected transport; run targeted/full venv tests. Acceptance: nonzero
running progress precedes one cancel, bounded partial artifacts and Stop, busy,
wrong-ID, EOF and failure handling, host passes counters unchanged.

## Implementation / semantics

`scripts/async_dispatcher.h` owns one `StreamProgress` containing five atomic
uint64 counters, reset under the dispatcher operation mutex at accepted start.
Poll/cancel include fixed-size `progress` with `stored_bytes`, `reads`,
`receive_elapsed_ns`, `packed_write_elapsed_ns`, `packed_flush_elapsed_ns`.
The sole native owner publishes counters; input/control thread reads atomics,
never accesses writer/files/USB. Individual counters are race-safe monotonic
within an operation, not a transactional multi-field snapshot. Finished response
publication synchronizes with owner completion, giving final counters. No
channel arrays, data payloads, queue growth or filesystem stat IO added to poll.

`stored_bytes` counts successfully written/flushed packed payload bytes, never
nominal samples, RX envelope bytes or metadata size. Progress updates after each
append and completed read, and before/after finalization. Metadata failure can
leave a flushed prefix: pre-finalization progress retains that count while the
existing STREAM_WRITE_ERROR response remains fail-closed. Writer constructor
failure produces zero progress and no receive/Stop command (no acquisition begun).
Receive `reads` counts returned read calls including zero-byte/error reads.

Elapsed counters are cumulative steady-clock nanoseconds measured around returned
receive calls, packed-file write calls and packed-file flush calls (including
final file flush). They exclude parameter/trigger/Stop writes, metadata IO,
parser/conversion work and file close. Buffered write/flush elapsed is NOT physical
disk bandwidth, durability, fsync, calibrated timing or a sole bottleneck finding.
Read time may include timeout wait. No throughput estimate or policy change.
Per-chunk flush,30ms settle,<=10ms reads,<=50ms sends,requested-duration deadline,
199MiB packed cap plus1MiB metadata reservation remain unchanged. Stop exceptions
now become cleanup_stop_ok=false instead of escaping the finalization path.

Tracked incremental-writer patch contains timing accessors/instrumentation;
tracked Stream patch passes dispatcher's progress to actual native owner.
Bootstrap copies updated headers, documents TASK057. Host/backend/service remain
thin, unchanged; test proves returned progress passes through exactly. All terminal
artifacts remain INCOMPLETE/UNKNOWN/null valid samples, success=false, no invented
COMPLETE, no tail removal or analysis readiness.

## Exact offline acceptance evidence

- `powershell -File scripts\bootstrap-native.ps1 -SkipTests`: exit0, twice;
  tracked patches reapplied from pinned CPP clean checkout, native CLI/tests built;
  device-opening upstream test executable NOT run.
- `cmake --build tests\native\build --config Release --target dl16-experimental-stream-test dl16-incremental-writer-test dl16-async-buffer-test --parallel 4`: exit0.
- Final extra failure modes rebuilt with `cmake --build tests\native\build --config Release --target dl16-experimental-stream-test --parallel 4`: exit0.
- `.venv\Scripts\python.exe -m pytest -q tests\test_experimental_stream.py tests\test_incremental_writer.py tests\test_async_buffer.py --basetemp artifacts\task057-targeted-work`: **37 passed in2.26s**.
- `.venv\Scripts\python.exe -m pytest -q --basetemp artifacts\task057-full-work`: **297 passed in17.44s**.
- `.venv\Scripts\python.exe -m compileall -q src`: exit0.
- `.venv\Scripts\python.exe -m ruff check tests\test_experimental_stream.py`: All checks passed.
- `git diff --check`: exit0.
- Native CLI SHA256 `C52F15AAE560A2F8B651C8DF63160167AF2A39806E35EFBE20EEEB3D63DCBEDC`.

Native synthetic integration polls nonzero >=64 bytes while running, checks actual
on-disk packed prefix, cancels once, validates final <=2048 bytes, all16 AA retained,
Stop successful, timing >0. Separate cases cover USB_ERROR,SHORT_RX,parameter/trigger
write failure,Order6 observation (not completeness),DEADLINE,failed Stop,existing
output directory,metadata write/finalization failure with bounded8B prefix;
second accepted start resets progress even after failure. EOF cancels/joins and
retains <=2048B. Busy/wrong-operation tests preserved. Synthetic transport evidence
is SYNTHETIC_OFFLINE, NOT HIL. Build/full logs: ignored
`artifacts\task057-{build,harness,full}.txt`; pytest work dirs removed after run.

## Parent-only single bounded physical gate (NOT executed)

Only parent, with existing confirmed CH8/14 safe wiring/shared ground/1.6V and GUI
closed, no competing owner, may run exactly ONE opt-in start at **1MHz,1000ms**
(maximum allowed in this gate; no PWM/wiring change). Require rebuilt hash above.
Start arguments: experimental_opt_in=True,
safety_confirmation=CONFIRMED_SAFE_WIRING_GUI_CLOSED,channels=[8,14],
sample_rate_hz=1000000,duration_ms=1000,threshold_voltage=1.6.

Poll <=200 times,10ms spacing and <=3s wall budget. On the FIRST running poll with
progress.stored_bytes>0, issue exactly ONE stream_cancel for that operation ID.
Retain that pre-cancel poll, timestamps and counters. Continue polling within the
same bounds, then close in finally. If finished before positive running progress,
no cancel gate accepted; no retry or second capture. Any error,short RX,cap,failed
cleanup or exhausted poll budget is a stop condition; close may cooperatively
cancel cleanup but must not be represented as accepted explicit cancel-after-data.
Stop/close ACK remains command observation, not certified physical idle.

Acceptance requires running nonzero progress followed by terminal CANCELLED,
bounded uncropped artifacts and successful Stop/close; retain all file/meta hashes,
worker hash/PID,journal,raw Order3/ACK/Order6,receive/write/flush elapsed under
`artifacts\hil\DL16-TASK-057\`.1MHz/1s nominal all16 payload2MB is planning only,
not actual count/completeness. Runtime199MiB cap unchanged; filesystem/OS operations
remain cooperatively bounded, not hard-real-time. Parent appends exact physical
results here/SOURCES/handoff; child has manufactured none. No retries,deadline
extension,endpoint clear,reset,driver or firmware operations.

Next: parent single cancellation-after-data gate; then evidence-led offline
backpressure/metadata cost evaluation, not speculative flush-policy relaxation.

Parent physical gate FAILED/NOT_CANCEL_ACCEPTED: one1MHz/1000ms Stream terminated SHORT_RX before positive running progress was polled and before cancel dispatch.65024 packed bytes,29reads,1024short bytes,receive38183200ns/write62200ns/flush1388000ns;Stopfields true,close success. Evidence artifacts/hil/DL16-TASK-057/records.json,journal,returned partial artifacts. No retry. Short raw bytes are not retained by this public path, so next work must preserve short-read raw framing diagnostically before choosing a conversion policy. No cancellation-after-data HIL pass claimed.
