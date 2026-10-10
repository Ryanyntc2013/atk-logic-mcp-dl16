# DL16-TASK-028 — restored-device depth-stop-v1 smoke

Base d5a43246c90af10b0dce190bac4a6003516de47b. Operator restored device at2026-10-11 07:08+08 and prior safe CH8/CH14 hardware authorization retained. Preflight info succeeded: Plus MCU1.9 FPGA2.22 USB2.0. No competing ATK/Logic process observed.

Executed existing two-request harness with DL16_NATIVE_DIAGNOSTICS=1 and DL16_EXPERIMENTAL_SESSION_LIFECYCLE=depth-stop-v1 using retained experimental CLI. Exactly CH8/CH14,20MHz,10ms,1.6V,immediate. No PWM configuration/reset/replay/fallback. Waveform source remains unverified.

## LOCAL_HIL observations

Both requests satisfied capture validity: ACK, offset, Complete, metadata exact[8,14] and200000 samples/channel. First elapsed~0.406s;second~0.140s. Each had200064 pre-crop samples/channel,200000 post-crop. Per-capture wake_observed=false as intended.

First order counts:1=208,2=24,3=1,4=1,5=162,6=4. Second:1=208,3=1,4=1,5=159,6=7. Second first-orders still begin `[6,6,6,4,5,5,...]`, but experimental depth-gated completion continued receiving subsequent channel data instead of ending the capture on those early Complete messages.

Harness verdict CAPTURE_VALIDITY_PASS,exit0,session.close returned successfully. Separate postflight native info also passed with correct model/firmware. This verifies fresh handshake after this block, not merely cached status. Stop write result is not surfaced, so do not claim transfer-level stop ACK or universal recovery.

## Evidence and interpretation

Ignored evidence under artifacts/hil/DL16-TASK-027/evidence/smoke-20261010-230834-b46a7d50396b4396ad85f117fca973f7, with full journal/step records and pre/post status. Original harness embeds task_id TASK-021; this report maps that harness identity to new experiment TASK-028 without rewriting originals. Binary SHA256 a5153ee40f08dcd97bc64f82c2e9f0e409e9f9411b8dec0c54aa1cd6a72bcb99. Manifest updated offline.

Strong evidence that ending on early Complete caused the previous receive loop to miss later data in this observed pattern. However lifecycle experiment changes three policies together (skip per-capture wake/flush, depth+markers completion, final stop), so no isolated single-change causality or exact LHX equivalence is established. No generation identifier proves absence of mixed-generation samples. Waveform quality was not evaluated; no numeric PWM/skew/calibration pass.

Outcome DONE bounded experiment, **CAPTURE_VALIDITY_PASS (2/2)**, NOT full session HIL acceptance or stability certification. Source implementation already validated by TASK027 offline tests/builds; this report-only task needs no extra software tests. Keep one-shot default/B6 retry and experimental opt-in. Next task: separately bounded 20-request repeatability plus waveform/source validation and postflight readiness, retaining all failures and stop telemetry. Do not silently promote defaults based on two successful requests. No push; operator LOCAL-HANDOFF edit preserved.
