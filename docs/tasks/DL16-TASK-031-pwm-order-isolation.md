# DL16-TASK-031 — PWM source order isolation

Baseline d569e95. Operator requested continue next step. Existing safe PWM0->CH8/PWM1->CH14 wiring and bounded hardware authority retained. No wiring/reset/firmware/driver changes. Existing reviewed PWM helper and depth-stop-v1 experimental binary reused.

## Experiments and results

Preflight info passed. Block A: only PWM0 start1kHz50percent, two captures. Both capture-valid,CH8 ten rising edges/window,median-period frequency1001.301692Hz,whole-window high fraction0.50013;CH14 all-low as expected with output1 not started. Frequency within1percent and duty within3percentage-point numeric criterion,not calibration.

After stopping both outputs, Block B: PWM1 start2kHz then PWM0 start1kHz,50percent, two captures. Both capture-valid,CH8 ten rising edges/window,1000Hz/high fraction0.5;CH14 all-low despite earlier PWM1 start success.

Both blocks stop0/stop1 returned exit0. Separate final info passed Plus MCU1.9 FPGA2.22 USB2.0. No replay/fallback/source rewire. Four total captures under two separately bounded sessions.

TASK030 had forward setup0->1 resulting CH14=2kHz and CH8 all-low. Together these experiments show the observed waveform follows the last-configured output under the current sequential helper operation. CH8 capture/signal path can acquire known PWM0, so prior missing CH8 is not evidence of a fixed channel capture failure. Cannot distinguish helper Device::open/close reinitialization versus command/device output mutual exclusion; no claim both outputs electrically cannot coexist.

## Evidence and limits

Ignored artifacts/hil/DL16-TASK-031, full journal/bundles/captures and source command/cleanup/status logs; waveform-summary.json records offline LSB-first median-period measurements. Runs pwm0-only/smoke-20261010-231837-0b82e9c58b1e470f803cafaada98f135 and reverse-order/smoke-20261010-231853-6e0c4559f2714e8aafeed3d85332b183. Reused harness task_idTASK021 is harness identity; mapped here to new TASK031. No source implementation modified; no additional suite required for report-only task. Manifest saved offline. All measurements uncalibrated; no generation provenance or full session HIL certification.

## Next engineering scope

Implement a reviewed bounded two-output configuration in ONE Device ownership interval, with regression vector coverage and explicit per-command/cleanup evidence, before claiming two-channel known-source acceptance. Do not use two standalone helper opens as proof of simultaneous PWM configuration. Current depth-stop-v1 single-active-channel waveform captures pass but remains experimental; keep one-shot/B6 defaults. Outcome DONE source-order isolation. No push; existing LOCAL-HANDOFF edit preserved.
