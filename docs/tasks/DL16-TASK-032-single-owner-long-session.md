# DL16-TASK-032 — single-owner long-session acceptance

Objective: complete a usable explicit opt-in long-session path with owned signal setup, observable cleanup and dynamic acceptance. Base cf8bc1d. Prior depth-stop-v1 gives valid repeated captures, but sequential standalone PWM helper opens leave only last-configured source visible. Implement bounded PWM commands in SAME native Device ownership interval, independently using documented reviewed PWM codec; do not copy unresolved-license LHX code.

Child owns native patch/tests/build only, offline, budget25calls/10min; parent owns harness/docs/HIL/commit. No USB reset/endpoint clear, power cycling, drivers/firmware or wiring change. Operator confirmed safe PWM0->CH8 PWM1->CH14 and autonomous bounded hardware permission. Existing LOCAL-HANDOFF edit untouched.

## Acceptance gates

1. Native PWM request validation before any open; fixed documented command0x17 only, output0/1 finite rate/duty. Track outputs this session configured, cleanup only those, expose transfer errors.
2. Depth-stop capture final stop result observable; failure cannot become a success claim. Existing host no-replay guarantees retained.
3. Fresh pin plus all patches build; USB-free native codec/contract tests; Python tests/compileall.
4. Same owner configures both sources1kHz/2kHz50percent,20 bounded captures with exact channels/counts and numeric frequency/duty verification. First failure stops.
5. Controlled timeout/error behavior and subsequent explicit request policy verified; no hidden reset/replay/fallback. Close owned outputs and device; fresh postflight info proves readiness.
6. Report gaps honestly. Numeric waveform bounds are uncalibrated and not absolute timing certification; same static/periodic signal alone cannot prove generation identity.

Do not silently promote one-shot default or remove B6. Long-session delivery may remain explicit opt-in if core gates pass; unverified triggers/model compatibility remain separate. Evidence ignored artifacts/hil/DL16-TASK-032. No push.

## Implementation and verified acceptance

Native session adds validated `pwm` command: `op=configure|stop`, `output=0|1`, integer frequency1..20000000, finite duty0..100. Configuration/stop use documented codec; output ownership tracks configured channels. Close stops owned outputs before device close and surfaces CLEANUP_FAILED; EOF cleanup failure exits nonzero. Python close propagates native errors. This is a native helper contract, not a new public MCP tool.

A separate observational patch exposes RAII final capture stop transfer outcome through CaptureEngine accessors, session dispatcher and JSON `cleanup_stop_attempted/cleanup_stop_ok`. No duplicate stop is added. Transfer failure turns a would-be success into incomplete error. Existing timeout stop plus final cleanup may both execute as prior lifecycle; no single-stop claim. Stop write success is host transfer success, not device ACK.

Seven tracked patches applied to a fresh pinned clone and VS2022/v142 build succeeded. USB-free PWM codec test covers exact payload, stop,NaN/infinity and limits. USB-free stop JSON seam passed. Python pytest **149 passed in6.48s**;compileall src/scripts and diff-check passed. Remote CI wired but not run. Original external binary untouched.

### Dynamic waveform acceptance

Same native owner configured PWM0=1kHz/PWM1=2kHz both50percent,then20 bounded captures. Both sources simultaneously present in every capture:CH8 exactly1kHz/high fraction0.5,CH14 exactly2kHz/high fraction0.5;exact200000 samples/requested channel,required integrity. First binary run PASS_WAVEFORM_UNCALIBRATED. Final stop-observable binary repeated20/20 PASS_WAVEFORM_UNCALIBRATED. close returned and separate postflight info passed. Final run dynamic-f13624f65ea64027b37a613c9e23f870,first run dynamic-bbc7c06669a24815bdba755ac6793147. Known waveform results distinguish source lifecycle from prior standalone helper ordering but do not prove electrical calibration or acquisition-generation identity.

### Timeout boundary and correction

Initial no-edge test using triggerCH0 while onlyCH8/14 enabled was rejected by capability validation; retained as invalid test setup, NOT a timeout or HIL pass. Corrected CH8 rising with owned sources stopped produced CAPTURE_TIMEOUT,final stop attempted/succeeded. A subsequent immediate request in SAME native session also timed out; preserve failure, do not claim seamless recovery.

Python backend now closes/invalidates any failed native acquisition without replay/fallback. A later explicit request may create a fresh native owner. Physical MCP-adapter test:CH8 no-edge timeout returned CAPTURE_TIMEOUT/session_invalidated=true,following explicit fresh-session immediate capture COMPLETE;final close and independent info passed. Full journal shows distinct owners. Host protocol failure similarly marks worker failed;next explicit operation replaces it. No automatic USB reset or failed-operation retry introduced.

## Delivery boundary

DONE: explicit opt-in long-session **buffer capture**,same-owner bounded PWM diagnostic controls,durable evidence,20-run dual-waveform normal path,fail-closed native timeout behavior and explicit fresh-owner recovery. Default remains one-shot withB6. Stream/RLE,universal firmware/model compatibility,unplug during capture,all trigger profiles and calibrated synchronization NOT accepted here. These do not block the scoped long-session buffer feature but must not be advertised as certified.

Use DL16_BACKEND_MODE=session and DL16_EXPERIMENTAL_SESSION_LIFECYCLE=depth-stop-v1 with the newly patched native binary;DL16_SESSION_JOURNAL_DIR enables audit. Native PWM requires manual reviewed setup JSONL,not automatic outputs on MCP startup. Python tests mock abnormal shutdown,framing and host timeout separately from physical tests. Evidence under ignored artifacts/hil/DL16-TASK-032/evidence with journals/captures/setup/cleanup/status/failure logs and manifest. No push;existing LOCAL-HANDOFF edit preserved.
