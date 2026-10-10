# DL16-TASK-030 — known-PWM repeatability and decision point

Baseline05fcfc4. Operator requested progress until decision point; previous safe PWM0->CH8/PWM1->CH14 authorization retained. Preflight fresh info passed. Existing reviewed tests/native/pwm_tool.cpp built helper used, no raw/arbitrary commands, no reset/driver/firmware/wiring changes. Binary helper SHA recorded by evidence manifest.

## Execution

PWM0 start1000Hz50percent,then PWM1 start2000Hz50percent, each helper returned ok. Explicit depth-stop-v1 plus diagnostic CLI,20 requests20MHz10ms1.6Vimmediate CH8/CH14, same session,first-error stop. Both outputs stopped in finally; each stop helper exited0. Separate postflight native info passed. Helper write success does not prove ongoing output or provide physical PWM ACK.

20/20 capture validity passed,required markers/exact200000 samples/channel. Retained artifacts analyzed independently LSB-first using numpy: frequency=20MHz/median rising-edge sample interval, high fraction over200000 samples. Numeric criteria1percent frequency and3percentage-point duty error around50percent; uncalibrated waveform criterion only.

- CH14: every capture20 rising edges,2000Hz,high fraction0.5, numeric PWM criterion passes.
- CH8: every capture0 rising edges,all-low samples, no frequency estimate, numeric PWM criterion fails.
- Overall waveform criterion FAIL; do not relabel as HIL_PASS. CH14 has real transitions, extending evidence beyond static TASK029. Does not disprove mixed-generation data.

Evidence ignored artifacts/hil/DL16-TASK-030/smoke-20261010-231602-fcc0b67bc8f94a60ba79a86a29aa8fc6: full journals/steps/capture bits plus waveform-summary.json; PWM start/stop/native status and cleanup logs at task root, manifest. Reused harness's task_idTASK021 is harness identity; mapping to new TASK030 preserved here.

## Decision point

Do NOT promote session default yet. Depth-stop-v1 consistently captures CH14 signal and remains postflight-ready in this block, but CH8 expected source is absent. Next investigation must separate source configuration/lifecycle from capture: bounded PWM0-only source check or reverse setup order, with recorded known-signal verification and cleanup. Each helper Device::open/close changes native initialization lifecycle, so PWM0 being affected by the second setup/open is a hypothesis, not established fact. Physical signal presence could also differ; don't request wiring changes or claim wiring fault without evidence.

Choose next scope explicitly: (A) isolate PWM setup ordering/output persistence under existing safe wiring, or (B) move PWM control into a reviewed single-owner native session interface with regression/cleanup telemetry. Option A is smaller and preferred for diagnosis; option B changes runtime command surface and ownership and requires a separate design. No hidden continuation past this decision point.

Outcome DONE experiment/report;capture-valid20/20;known-source waveform overall FAIL;default one-shot/B6 retained. No software edits this task; reuse previously tested binaries/harness. No extra suite needed for report-only changes. No push/operator LOCAL-HANDOFF edit preserved.
