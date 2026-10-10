# DL16-TASK-027 — independently implemented depth/stop session experiment

Requested by operator: implement and test a version following documented LHX lifecycle principles. Base fd71292. Reference LHX pin 8d7c209c1e3b13923620bb34cec915291a749612 from TASK-019: initialize once, ordinary acquisition by requested data depth, stop in final cleanup. No source copied/translated; no unresolved-license code incorporated.

## Implementation

Explicit opt-in native process environment `DL16_EXPERIMENTAL_SESSION_LIFECYCLE=depth-stop-v1`. Only JSONL session dispatch sets the config flag; one-shot and default session remain unchanged. Experimental capture skips per-request wake/flush, relying on Device::open initialization, requires ACK + order3 + Complete AND sufficient requested-channel samples after computed offsets, and sends existing stop frame at end through scope cleanup. A Complete alone no longer terminates experimental RX. Existing bounded host/device timeout and incomplete errors remain. No USB reset, firmware, driver or arbitrary vendor command.

This is NOT an exact LHX port: existing pinned native framing, crop, marker validation, device-open/close and watchdog remain. Multiple policy changes are intentionally grouped to test the requested lifecycle; success cannot isolate which change matters. No generation ID proves batch provenance. Enough samples/markers can still represent mixed generations; waveform validation and repeatability are mandatory before acceptance. Stop transfer return is currently not surfaced and cannot be claimed successful device stop from destructor execution alone.

Patch applies after base/session/diagnostics/prearm. Isolated build and second fresh pinned clone applying all five patches built VS2022/v142 exit0. USB-free experimental criterion test checks zero/insufficient samples, missing ACK/offset/Complete and offset underflow. Python pytest:135 passed in5.31s. compileall src/scripts and diff-check passed. Upstream hardware-open tests not run; original operational executable untouched. Native criterion tests wired into existing CI, remote CI not run.

## Physical test gate

Readiness probe before capture failed with512-byte MCU response and first16 bytes zero. No experiment capture performed, no retry/reset. HIL_NOT_RUN; requires operator restore then fresh readiness and at most two captures using retained experimental CLI under ignored artifacts/hil/DL16-TASK-027/evidence. Source declaration waveform unverified; no PWM configured by task.

Candidate command after restored readiness (operator-authorized safe CH8/CH14):

```powershell
$env:DL16_NATIVE_DIAGNOSTICS='1'
$env:DL16_EXPERIMENTAL_SESSION_LIFECYCLE='depth-stop-v1'
.\.venv\Scripts\python.exe scripts\dl16_session_smoke.py --taskdir artifacts\hil\DL16-TASK-027\evidence --cli-path artifacts\hil\DL16-TASK-027\evidence\atk-dl16.exe --live --confirm-connected --confirm-wiring --confirm-voltage --confirm-signal-configured --source-declaration 'Operator restored safe CH8/CH14 wiring; waveform unverified'
```

Outcome: DONE offline experimental implementation / NEEDS_HUMAN_HIL. No default change, B6 retained. Original LOCAL-HANDOFF edit preserved. No push.
