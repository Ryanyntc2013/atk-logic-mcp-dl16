# HIL operating rules (DL16-TASK-A6)

Binding for every hardware session. Hardware operations require an explicit operator
statement that the DL16 is connected and the wiring context (AGENTS.md).

## Enforced in code

- **Channel cap.** `CaptureRequest.validate()` refuses more than 4 channels unless the
  operator sets `DL16_MAX_CHANNELS` (1–16). Reason: 16-channel acquisition previously
  wedged the device; the root cause is not yet fixed.
- **Retry bound.** Post-capture open failures are retried at most `MAX_ATTEMPTS` (3)
  times with linear backoff; every retry is recorded in `retry_log` and `warnings`.
  Timeouts and incomplete evidence are never retried.
- **Pipeline safety.** Native CLI output is parsed as complete JSON; no truncating
  pipeline (`| Select-Object -First N`) is used around a capture. A host-killed capture
  returns `HOST_TIMEOUT` and must be followed by a status check before the next capture.

## Procedural (not yet enforced)

1. Start every session with `status`. Stop if `connected` or `ready` is false.
2. Prefer one or two channels. Use a 3 s trigger timeout for gated tests.
3. Do not run the ATK-Logic GUI at the same time as an MCP session.
4. Do not run `send_raw`, arbitrary vendor commands, firmware/bootloader opcodes, USB
   resets, endpoint clearing, or driver changes without explicit human approval.
5. After every hardware block, record the evidence with
   `scripts/hil-evidence.ps1 -TaskDir artifacts/hil/DL16-TASK-xxx` and, if device
   identity is needed, add `-IncludeDeviceInfo` (serial numbers are redacted).
6. Record the session result in `docs/HIL-PHASE-B-STATUS.md` (single source of truth).
