# DL16-TASK-066 — Physical HIL validation plan

**Status: SCRIPT_READY / HIL_NOT_RUN.** This document/script do not authorize hardware use. Live execution requires an explicit on-site operator statement that a DL16 is connected, with confirmed wiring, safe voltage and exclusive hardware control under AGENTS.md and docs/HIL-OPERATING-RULES.md.

Branch: fix/DL16-TASK-066-offline-correctness
PR: https://github.com/Ryanyntc2013/atk-logic-mcp-dl16/pull/1
Script: scripts/dl16_task066_hil.py
Offline tests: tests/test_task066_hil_harness.py

## Test goals

1. Normal bounded 1kHz/2kHz PWM Buffer and Stream self-test.
2. Inject a Python-level PWM1 configuration rejection **after PWM0 has actually been configured**, then confirm actual native stop and close.
3. Inject Buffer failure after both PWM outputs actually start; verify cleanup.
4. Start real Stream, inject the first poll failure at Python boundary, confirm real cancel, stop and close.
5. Verify physical PWM-off with an independent oscilloscope or other independent analyzer, not just USB or software ACK.

Faults are injected at the Python application boundary only. They never fake native PWM stop, session close or USB command success. The script does not test cable-pull, resets, unpowered FPGA or true link loss.

## Before live execution: mandatory safety conditions

- Local Windows 10/11, Python venv, patched pinned native atk-dl16.exe, device connected.
- PWM0 to CH8, PWM1 to CH14, shared GND; operator checks actual signal voltage is <=3.3 V CMOS and suitable for the DL16 inputs.
- No sensitive external DUT on PWM outputs; separate oscilloscope probes physically observe **both** PWM outputs.
- Official ATK GUI closed; all other MCP/Agent/device-control processes stopped. Python's owner check does **not** guarantee interprocess exclusion.
- The operator can independently shut off device outputs if unexpected activity persists. Do not unplug/replug, power cycle, reset USB, change driver, send raw commands or rewire automatically.
- No cases run automatically. One command = one case. Stop immediately on any FAIL or unclear output.

## Offline mode — safe with disconnected device

In an interactive local terminal, on this PR branch, run the following. None should access USB:

~~~powershell
git switch fix/DL16-TASK-066-offline-correctness
.\.venv\Scripts\python.exe -m pytest -q tests/test_task066_hil_harness.py tests/test_task066_offline_safety.py
.\.venv\Scripts\python.exe scripts/dl16_task066_hil.py --case normal
.\.venv\Scripts\python.exe scripts/dl16_task066_hil.py --case pwm1-reject
.\.venv\Scripts\python.exe scripts/dl16_task066_hil.py --case buffer-reject
.\.venv\Scripts\python.exe scripts/dl16_task066_hil.py --case stream-poll-error
~~~

Expect HIL_NOT_RUN, OFFLINE_PLAN_ONLY. No run folder or device connection.

## Live command (ONLY after operator authorizes actual hardware)

~~~powershell
$env:DL16_BACKEND_MODE = "session"
$env:DL16_CLI_PATH = (Resolve-Path ".\external\ATK-Logic-Mcp\build\Release\atk-dl16.exe").Path
$case = "normal"
.\.venv\Scripts\python.exe scripts/dl16_task066_hil.py --case $case --execute --confirm-connected --confirm-loopback --confirm-voltage --confirm-gui-closed --confirm-exclusive-owner --confirm-scope
~~~

Run one of normal, pwm1-reject, buffer-reject, stream-poll-error. The script requires interactive typed RUN-DL16-066 before using USB, and manual observation of both PWM output pins after the run. It refuses background/noninteractive Agent execution.

| Order | Case | Real operation | Expected result |
|---|---|---|---|
| A | normal | Real PWM0 1kHz + PWM1 2kHz; Buffer 20MHz 20ms; Stream 1MHz 100ms | success, DIAGNOSTIC_PASS_UNCALIBRATED |
| B | pwm1-reject | PWM0 real configure, PWM1 fake rejection at Python boundary | PWM_CONFIG_FAILED; actual stop + close |
| C | buffer-reject | Both PWM channels real configure, Buffer blocked before native capture | BUFFER_CAPTURE_FAILED; actual stop + close |
| D | stream-poll-error | Real Buffer and Stream start; one application poll rejected | STREAM_POLL_FAILED; actual cancel + stop + close |

## PASS/FAIL gates for every case

- Return outcome and error code match the expected case.
- Software cleanup_ok is true and native session close reported closed=true.
- Postflight new owner can query connected/ready, then closes without replug/reset.
- Independent scope detects no PWM toggling after shutdown on BOTH PWM0 and PWM1.
- A real scope screenshot/path or documented observation note is included in report.
- No automatic USB reset, endpoint-clear, driver update or firmware operation.
- No claims of absolute synchronization timing calibration.

If any condition fails: verdict FAIL_OR_UNVERIFIED, **STOP, DO NOT RUN NEXT CASE**. Preserve evidence and use the approved physical shutoff procedure if PWM remains active.

## Evidence and audit

Each live run records a unique artifacts/hil/DL16-TASK-066/<UTC>-<case>-<nonce>/ directory:

- preflight.json: code hash, pinned native executable SHA-256 and operator confirmations
- result.json: native operations, reported cleanup, fault injection trace and fresh postflight status
- operator_observation.json: scope observation, evidence note, separate PASS_UNCALIBRATED or FAIL_OR_UNVERIFIED verdict
- SHA256SUMS.txt: hash manifest for evidence files
- data/: resulting Buffer or Stream captures where applicable

If oscilloscope screenshots are copied in after the script exits, rerun scripts/hil-evidence.ps1 -TaskDir <run-directory> to update hashes (WITHOUT IncludeDeviceInfo) and archive the screenshot. The operator must assess independent physical off-state; a software ACK is not sufficient.

**Acceptance status remains NEEDS_HUMAN_HIL until all four real cases pass with independent physical evidence.** Record exact code/native binary SHAs, firmware, wiring, results and residual uncertainty in docs/HIL-PHASE-B-STATUS.md. Keep PR draft until reviewed and authorized for merging.
