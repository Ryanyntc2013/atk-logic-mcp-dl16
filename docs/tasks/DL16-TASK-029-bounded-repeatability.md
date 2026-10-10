# DL16-TASK-029 — depth-stop-v1 bounded repeatability

Baseline dafdb972. Extend existing smoke harness with explicit --requests2..20, default2 retained; reject invalid/bool/noninteger block sizes before launch. All steps remain durable and first failure stops. New mocked20-success/second-failure and bound tests. This is not an unlimited soak or default promotion.

## Validation

Python pytest142 passed in5.99s; targeted harness19 passed in1.91s; compileall src/scripts and diff-check passed. Existing final experiment binary reused, no native changes.

## Authorized hardware block

Fresh preflight info passed Plus MCU1.9 FPGA2.22 USB2.0. Operator autonomous safe CH8/CH14 authorization retained. Explicit DL16_EXPERIMENTAL_SESSION_LIFECYCLE=depth-stop-v1 plus diagnostics, 20 requests,20MHz/10ms/1.6V/immediate. No PWM configured/reset/replay/fallback. Same owned session,20/20 CAPTURE_VALIDITY_PASS,200000 samples/channel/exact channels/required integrity markers. Elapsed0.125..0.438s. close returned successfully; separate postflight info passed. Stop transfer result remains unavailable.

Evidence ignored artifacts/hil/DL16-TASK-029/smoke-20261010-231252-151b7b20e29f4d339c6177d330e64080, full journal/per-step records/bundle, pre/post status, console and SHA256 manifest. Original harness task_id TASK021 is harness identity, not reused experiment ID. Readiness and capture responses saved natively, not reconstructed. Binary unchanged from TASK028 SHA256 a5153ee40f08dcd97bc64f82c2e9f0e409e9f9411b8dec0c54aa1cd6a72bcb99.

## Waveform boundary

Offline numpy.unpackbits(bitorder=little) inspection of every requested channel artifact: all20 CH8/CH14 captures contain200000 low samples and zero transitions. Full offline summary retained as offline-waveform-summary.json. No known PWM frequency present, no numeric frequency/skew/trigger gating pass. This is static-input capture repeatability only. Static identical data cannot disprove mixed-generation samples. It is not evidence that operator wiring is incorrect or PWM hardware broken; outputs were not configured by task.

Outcome DONE bounded repeatability,20/20 capture-valid,postflight-ready; session remains experimental and not fully HIL accepted. One-shot default/B6 retained; no push. Original LOCAL-HANDOFF edit preserved.

Next task: bounded documented PWM source setup using existing reviewed tests/native/pwm_tool.cpp (not arbitrary command), source cleanup evidence, and verify frequency/duty/transitions across session trials. Include stop transfer telemetry and stale-generation testing before promoting session defaults. Do not describe static repeatability as known-signal waveform validation.
