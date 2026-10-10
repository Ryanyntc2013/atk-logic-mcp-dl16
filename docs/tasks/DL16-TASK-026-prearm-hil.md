# DL16-TASK-026 — restored-device pre-arm telemetry HIL

Baseline `6b6117592698a0a0aaeeaf06f2edb4ca3516835a`. Operator restored device and authorized continuation at 2026-10-11 06:53 +08. Readiness passed (Plus MCU1.9 FPGA2.22 USB2.0); no competing ATK/Logic process observed. No reset/driver/firmware/PWM configuration performed.

Reused bounded two-request harness with explicit retained TASK-025 CLI and `DL16_NATIVE_DIAGNOSTICS=1`. Exact CH8/CH14,20MHz,10ms,1.6V,immediate. Signal waveform remains unverified. Binary SHA256 `46f096965ff9b09c88b7be815d6a517ce738bc66c6b84e670ae935ad4b5bf004`.

Evidence run: ignored `artifacts/hil/DL16-TASK-025/evidence/smoke-20261010-225406-c3aac790ed494229b29a747272753cf6/`. Original reused harness task_id=TASK-021 is harness identity; this report maps the new experiment to TASK-026, preserving originals unchanged.

## Results — LOCAL_HIL / HIL_FAIL

Both requests: wake_observed=true, wake_write_ok=true. Each wake internal flush AND explicit flush performed 50 successful 2048-byte reads (102400 bytes per flush), errors=0, ended_empty=false, limit_reached=true. Existing bounded flush therefore did NOT observe an empty read in either request.

First capture passed: elapsed~0.438s,46 receive reads/753664 bytes; order counts1=208,2=3,3=1,4=1,5=153,6=2. CH8/CH14 each200064 before crop and200000 after.

Second capture failed: elapsed~0.109s,one16384-byte receive read; orders `[6,6,6,4,5,5,5,5]`; no channel data, zero samples before/after crop. Stop-on-failure, no third capture/replay/fallback. Session close returned successfully; physical post-close readiness not probed.

## Interpretation

Flush reaching cap cannot be labelled successful endpoint clearing. However first capture has the same cap saturation and succeeds, so cap saturation alone does not explain second capture failure. Flush data content is not retained/decoded; errors=0 and positive lengths do not establish whether these are padding, active traffic or residual frames. No acquisition generation ID establishes ownership of early Complete. Do not enlarge flush/drain limits or ignore Complete to manufacture a pass.

Next bounded investigation: capture a small fixed preview/fingerprint of existing flush reads and compare physical/native transfer accounting, or establish a tested lifecycle/completion contract against pinned sources. No new hardware experiments until a bounded hypothesis/test is specified. One-shot default/B6 mitigation preserved. Stable session still unaccepted.

Delivery: diagnostic experiment/report DONE. No software behavior changed; reused previously validated binary/harness. Offline SHA256 manifest updated after experiment. No waveform or timing certification.
