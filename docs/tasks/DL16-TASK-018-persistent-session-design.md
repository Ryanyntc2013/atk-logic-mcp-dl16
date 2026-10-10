# DL16-TASK-018 — persistent native JSONL session design

**Status:** TASK-018-A/B implemented; 018-C ran and failed persistent-session capture acceptance. One-shot comparison passed 20/20. Keep one-shot as default and retain B6 retry; session lifecycle requires further investigation.
**Scope:** replace per-operation native CLI process startup with one owned, persistent native
process that serializes `status` and buffer-capture requests over JSON Lines (JSONL).
**Evidence boundary:** B6 is currently retry-contained, not fixed. This design does not claim
that keeping a process or USB handle open repairs the firmware/device-info behavior.

## Motivation and evidence

The current Python adapter starts a new native process for each `info` or `capture` call. The
CLI constructs a new `Device`, opens it, queries MCU/FPGA information, and exits after one
operation. `Device` destruction calls `close()`, which sends FPGA sleep and releases the USB
interface. The next operation repeats the full open/query/wake sequence.

DL16-TASK-002 B6 observed 10 first-attempt failures in 20 sequential captures, alternating
after successful captures. The error was `Failed to parse FPGA device info packet`; one
bounded retry of the operation recovered in the recorded 20/20 follow-up. This is a failure
of the device-info query performed on a fresh open after capture. A persistent session avoids
that repeated open/query path between requests, but may expose a different long-lived-device
failure mode and must be validated independently.

Relevant implementation points in the pinned source:

- `cli/main.cpp`: `info` and `capture` each create a local `Device`; `capture` runs once and
  then returns from `main`.
- `core/src/device.cpp`: `Device::open()` opens the transport, calls `query_info()`, and wakes
  the FPGA. Failure closes the transport. Destruction/close sleeps the FPGA and releases it.
- `core/src/capture.cpp`: `execute_capture()` uses the already-open `Device` and returns a
  complete `CaptureResult`; capture timeout is separate from host process lifetime.
- `core/src/usb_transport.cpp`: the transport holds the interface and an OS-level per-port
  ownership lock until close.

## Proposed protocol

One native process accepts exactly one UTF-8 JSON object per input line and emits exactly one
UTF-8 JSON object per request on stdout. Diagnostics and progress go to stderr. Each request
and response carries a caller-supplied `request_id` so the parent can correlate responses.
Requests are processed serially; no command may interleave with an active capture.

Initial command set:

1. `hello` — protocol version, native build identity, and supported command list; does not
   open USB.
2. `status` — reports session/transport state and cached device information. It does not
   reopen the device or re-run `query_info()`.
3. `capture` — accepts the existing validated capture configuration, output directory,
   trigger position, and device timeout; returns the existing full capture result schema.
4. `close` — acknowledges shutdown, then closes the device and exits successfully.

Example (illustrative schema, subject to implementation review):

```jsonl
{"request_id":"r1","command":"hello","protocol":1}
{"request_id":"r1","ok":true,"protocol":1,"commands":["status","capture","close"]}
{"request_id":"r2","command":"status"}
{"request_id":"r2","ok":true,"session":"ready","transport_open":true,"device":{"model":"DL16 Plus","mcu_firmware":"v1.9","fpga_firmware":"v2.22"}}
```

The exact schema must be defined once in the implementation and mirrored by contract tests.
Unknown commands, malformed JSON, missing/duplicate IDs, invalid request fields, and
unsupported protocol versions return a typed error response when framing remains recoverable.
An invalid or overlong line is rejected with a bounded response or causes a documented
protocol error; it must never be treated as a partial capture request.

## Ownership and lifecycle

- Python owns one child process per MCP server process. The child is started lazily on the
  first native operation; it is not a global machine service and is not detached.
- Exactly one native session may own the DL16 USB port. The native transport's existing
  per-port lock remains the final cross-process exclusion. A second MCP instance receives a
  typed `DEVICE_BUSY` result; it must not kill the first instance or steal its handle.
- The native session opens one `Device` at startup/first device operation and holds it across
  sequential `status` and capture calls. `status` reports cached open state and cached device
  information. It does not claim a fresh live FPGA query; disconnects are surfaced by a later
  USB operation and invalidate the session.
- A valid completed capture returns its normal artifact/result and leaves the session open.
  It must not sleep/reset the FPGA as a per-request cleanup action. `close` and orderly
  process shutdown call `Device::close()` exactly once.
- Parent shutdown closes stdin, waits a bounded grace interval for process exit, then
  terminates only the child process it created. No process-name matching, `taskkill` of
  unrelated processes, USB reset, endpoint clearing, or driver changes.
- One request at a time. Calls from Python threads are guarded by a lock and receive one
  complete response each. No concurrent captures or priority interleaving.
- A configured host timeout kills the owned child and marks the session `failed`; it does not
  replay the request. In particular, a timed-out capture is never automatically repeated,
  because capture has physical side effects and the first operation may have completed even
  if its response was lost.
- On child exit, broken pipe, malformed response, or request-ID mismatch, Python fails the
  active request with `SESSION_PROTOCOL_ERROR`/`SESSION_EXITED`, marks the session unusable,
  and requires a new explicit operation to create a new child. It does not automatically
  retry a capture. The existing narrow B6 retry policy may remain only for the legacy
  one-shot backend until comparative HIL evidence supports removing it.
- No automatic idle timeout in the first implementation. An idle timeout risks silently
  changing FPGA/USB ownership between adjacent MCP calls. Explicit `close` and parent
  shutdown are the initial lifecycle boundaries.

## Implementation sequence

### 018-A — offline protocol and native refactor

1. Refactor the native CLI command bodies into testable handlers while preserving the current
   one-shot CLI behavior and JSON schema.
2. Add `session --jsonl` using the pinned patch workflow, with one long-lived `Device`, strict
   line framing, serial dispatch, request IDs, bounded line size, and stdout-only JSONL.
3. Add native tests for startup/close, multiple sequential commands, malformed/unknown
   requests, request-ID correlation, no interleaving, capture errors, and close-on-exit. Tests
   use injected/fake transport or a command-dispatch seam; they must not require a DL16.
4. Extend the existing Windows native CI to build and run session tests from a clean pinned
   checkout. Preserve the current CLI smoke and protocol vector tests.

### 018-B — Python process owner and contract tests

1. Add a small session manager owned by the MCP server process: lazy start, serialized
   request/response, request IDs, bounded reads/writes, child ownership, explicit close, and
   typed failure states.
2. Route `logic_status` and `logic_capture` through the session when enabled. Keep the
   one-shot backend available behind an explicit compatibility setting for rollback and
   A/B comparison; do not silently fall back to one-shot after an ambiguous session response.
3. Add mocked-process tests for startup, successful multi-request reuse, malformed JSON,
   child exit, host timeout without replay, orderly shutdown, and concurrent Python callers.
4. Run `python -m pytest -q` and `python -m compileall -q src`.

### 018-C — bounded LOCAL_HIL comparative validation

Run only when the operator confirms the device is connected, the known wiring is present,
and the ATK-Logic GUI is closed. Current confirmed wiring is PWM0 -> CH8 and PWM1 -> CH14;
do not require or assume a CH0 loopback. Use these two channels at 20 MHz, 10 ms, and
complete status checks before and after each block. Save evidence under
`artifacts/hil/DL16-TASK-018/` with the evidence-manifest script.

1. With the confirmed PWM0->CH8/PWM1->CH14 loopbacks, configure PWM0 at 100 Hz and PWM1 at
   1007 Hz, both 50% duty. Capture channels 8 and 14 at 20 MHz for 10 ms with immediate
   trigger. This is a bounded 200,000 samples/channel per capture; default 4-channel safety
   cap remains in force.
2. Verify session startup/hello/status. If comparing USB exclusivity, a second worker may
   be launched only as a probe and must receive `DEVICE_BUSY`; do not terminate or disturb
   the owning session.
3. Run 20 sequential captures in one persistent session. Record every request ID, result,
   latency, retry/log state, artifact completeness, process PID, and session state.
4. If device state remains healthy, stop/restart only the approved PWM outputs as needed,
   then run a separate 20-capture one-shot comparison with the exact same channels, rates,
   duration and trigger. Status-check between blocks.
5. Pass criteria: 20/20 complete captures within the persistent session; no child restart,
   request/response mismatch, data-integrity downgrade, or silent retry; status remains
   transport-open between captures. Any failure is retained as evidence and stops the block.
6. Only if persistent-session HIL passes and the comparison supports it, propose a later
   change to retire the B6 retry. Do not remove the retry in TASK-018-A/B based on theory.

The 20/20 criterion validates this device/firmware and test configuration only. It does not
prove all capture modes, all firmware versions, or a general B6 fix.

## Explicit non-goals

- Stream mode, hardware RLE, raw wire-packet persistence, multi-device support, parallel
  captures, and remote/network session control.
- Protocol redesign beyond local JSONL framing and typed session results.
- USB recovery/reset, driver manipulation, firmware operations, arbitrary vendor commands,
  or automatic capture replay.
- Claiming that process persistence alone fixes the FPGA's post-capture device-info behavior.

## Acceptance checklist

- [ ] JSONL request/response schema and protocol version documented and tested.
- [ ] Child lifetime and USB ownership are explicit; no orphaned child after orderly shutdown.
- [ ] Multiple requests reuse exactly one child and one open `Device`.
- [ ] Malformed/unknown input and response framing fail closed with bounded output.
- [ ] Timeout, child crash, and disconnect do not automatically replay capture.
- [ ] Legacy one-shot path remains available until HIL comparative evidence is accepted.
- [ ] Native CI and all offline Python tests pass from clean checkout.
- [ ] LOCAL_HIL evidence and checksums are recorded before changing B6 retry status.

## Current task status

TASK-019 correction: the session parser appended CH8/CH14 to CaptureConfig's
default CH0/CH1. Thus the prior session/one-shot runs were not identical-channel
comparisons; their observed failures remain valid but the physical cause is not
established. The parser and missing-header patch packaging are now corrected and
verified by native regression and a genuinely fresh pinned clone build. See
`DL16-TASK-019-session-remediation.md`. No new capture validation has been run.

### Completed offline implementation

- Native worker: tracked `scripts/patches/atk-dl16-session.patch`; `bootstrap-native.ps1`
  applies it after the base local patch with `git apply --check`. JSONL protocol version 1
  supports hello/status/capture/close, serial dispatch, bounded lines, request IDs, strict
  object parsing, and typed malformed/unknown/invalid-request responses.
- Native parser and CLI contract tests are part of the pinned synthetic suite: 32/32 pass.
- Python `NativeSession` owns one child process, uses one reader thread and serialized
  request lock, verifies request IDs, and invalidates/terminates the owned child on timeout,
  EOF, malformed response, oversized line, or correlation failure. It never retries or
  replays capture requests.
- `DL16_BACKEND_MODE=session` opts into session routing for status/capture. Default remains
  `oneshot`; failures do not silently fall back. Process shutdown closes the owned worker.
- LOCAL_HIL after wiring confirmation PWM0->CH8/PWM1->CH14, frequencies 100/1007 Hz, both
  50%, capture CH8+CH14 at 20 MHz / 10 ms. The second-worker ownership probe returned
  `DEVICE_OPEN_FAILED` with port-claimed text and exited without stealing the active handle.
- First HIL block exposed a real serialization defect: the on-device capture completed and
  wrote `cap_1791641573277_8694`, but multiline nested capture JSON made the outer JSONL
  response invalid. No replay was performed. JSON-aware whitespace compaction was added,
  covered by native unit tests, and verified in a real session smoke capture.
- The repeated persistent-session block then stopped at run 2: run 1 succeeded
  (`cap_1791642349999_9388`); run 2 returned `INCOMPLETE_CAPTURE`, with Complete observed but
  every enabled channel at 0/200000 samples. The request was not retried. The session block
  therefore FAILED its acceptance criteria.
- Separate one-shot comparison: 20/20 captures COMPLETE with 200000 samples on CH8 and CH14.
  The legacy narrow B6 retry was visible on 16/20; all recovered on attempt 2. Four were
  first-attempt successes. All 21 one-shot artifacts (smoke + 20) have complete metadata.
- Read-only final status was connected/ready. Both PWM outputs were stopped. Evidence and
  SHA256 manifest are under ignored `artifacts/hil/DL16-TASK-018/`.
- Verification on Windows: `bootstrap-native.ps1` (clean reset + ordered patches) succeeded;
  native suite 32/32; JSONL 6-request hello/malformed/unknown/invalid-capture/invalid-trigger/
  close smoke passed. Python suite 107 passed; compileall and diff checks passed.
- Current confirmed wiring is PWM0->CH8 and PWM1->CH14; no wiring change was needed. Session
  is NOT accepted as a capture backend. Keep `DL16_BACKEND_MODE=oneshot` as default and keep
  the B6 retry. Next step is offline investigation of post-capture sample-store/session
  lifecycle and a deterministic native regression reproducing the zero-sample Complete
  result; any subsequent HIL needs a fresh bounded approval and must stop on first failure.
