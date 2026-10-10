# DL16-TASK-025 — pre-arm wake/flush telemetry

Baseline `984770ddfea4987959de11e109e938bf485dda38`. TASK-023 second capture observed three Complete messages before ACK/progress, no channel data and zero samples before crop. No capture-generation ID proves the Complete messages are stale.

Objective: extend opt-in bounded diagnostic observations to existing pre-arm wake and flush paths, capturing ignored transfer errors, read byte counts, flush stopping reason/iteration-cap status and bounded previews if implemented. Observe wake's internal flush and capture's explicit subsequent flush separately. Do not change commands, wait times, read lengths/count limits, return semantics, stop/FPGA sequencing, capture termination or replay policy.

Implementation/acceptance: reviewable tracked patch applied after TASK-022 diagnostics; isolated fixed-pin fresh build; USB-free telemetry mock/seam tests; Python pytest/compileall. Do not invoke upstream hardware-open suite as offline verification. Preserve binary and test evidence before cleaning scratch clones. Parent reviews before a new live block; current device readiness after TASK-023 is unknown, so no unrecorded captures. Operator LOCAL-HANDOFF modification remains untouched.

Evidence location: ignored `artifacts/hil/DL16-TASK-025/`. Native source remains pinned GPL backend; no LHX code copied/translated. Short/zero pre-arm data or a Complete-like byte preview is not by itself packet ownership proof. No automatic reset, power cycle, endpoint clear, firmware/driver operation or additional drain.

## Delivery and validation — 2026-10-11

The child agent entered a repeated invocation loop without persisted implementation and was stopped; parent implemented the patch directly. The loop did not operate hardware. Do not credit the child with this delivery.

`DL16_NATIVE_DIAGNOSTICS=1` now extends the v1 JSON additively: `wake_observed`, `wake_write_ok`, `wake_flush` and `explicit_flush`. Each flush reports reads, bytes, errors, `ended_empty`, `limit_reached` and at most 50 read sizes. No raw previews added. Error count includes failed/timeout reads without interpreting all as device faults. An empty read may be a timeout; it is not proof of a physically empty endpoint. Unobserved fields remain distinguishable by zero read count/wake_observed=false. Original return behavior (including ignored write/read errors), 5 ms timeout, 50-read cap and command sequence unchanged.

New tracked patch applies after base, session and diagnostics. Two isolated fixed-pin builds with VS2022/v142 succeeded, including a second fresh checkout applying all four tracked patches. Upstream hardware-open test executable was not run. USB-free aggregate/JSON seam compiled and exited 0; it tests 50-entry bounding, byte/error aggregation and flush ending/cap state. Python `pytest -q`: **135 passed in 5.36s**. `compileall -q src scripts` and `git diff --check` passed.

Authorized readiness probe with retained telemetry CLI again failed with a 512-byte MCU reply whose printed first 16 bytes were zero. No subsequent capture, retry/reset or additional drain performed. Physical pre-arm telemetry capture **HIL_NOT_RUN**; current readiness **BLOCKED**. No firmware-damage inference. Evidence retained in ignored `artifacts/hil/DL16-TASK-025/evidence/` with binary, DLL, offline seam output, readiness output and manifest; disposable source clones are removed after delivery.

Outcome: **DONE (offline implementation)** / **BLOCKED (physical validation)**. One-shot default and narrow B6 mitigation retained. Next physical step requires restored readiness before a new two-request diagnostic block. Do not promote session or change completion policy based only on missing pre-arm evidence.
