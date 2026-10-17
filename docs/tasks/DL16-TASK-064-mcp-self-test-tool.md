# DL16-TASK-064 — automated hardware self-test tool for MCP

> Current contract (TASK-066): a numeric pass is `DIAGNOSTIC_PASS_UNCALIBRATED`, and the
> tool requires `safety_confirmation="CONFIRMED_SAFE_WIRING_GUI_CLOSED"`. The `HEALTHY`
> string and `confirm_safe_wiring=True` below are this task's historical report, not a
> calibration certificate.

State: **DONE (implemented, verified with synthetic tests and confirmed via physical HIL run)**.
Base: `35ae4bb`. Single physical owner loopback verification.

## Objective

In TASK-060 through TASK-063, the Buffer and Stream capture pipelines, cross-read carry-over buffering, and offline analysis integration were validated.
TASK-064's objective was to:
1. Provide a single end-to-end automated hardware health diagnosis tool `logic_self_test(confirm_safe_wiring: bool = False)` in `service.py` and `server.py`.
2. Guard invocation with mandatory `confirm_safe_wiring=True` (requiring CH8 to PWM0 and CH14 to PWM1 loopback with GUI closed).
3. Automate the complete verification chain:
   - USB link and hardware status inquiry.
   - Dual-channel PWM configuration (1000Hz on CH8, 2000Hz on CH14).
   - High-speed 20MHz Buffer capture with frequency and jitter validation.
   - 1MHz Stream continuous capture with frequency validation on CH8 and CH14.
   - Safe session teardown and PWM shutdown.
   - Output structured diagnostic report with overall health verdict.

## Verification results

- Synthetic regression:
  - `python -m pytest -q`: 309 passed in 15.71s (including safety confirmation rejection test).
  - `python -m compileall -q src`: clean (0 errors).
- Physical verification:
  - Ran `logic_self_test(confirm_safe_wiring=True)` on physical DL16 Plus.
  - Results:
    - Overall health: `HEALTHY`.
    - Buffer capture: `ok: true`, CH8 frequency 1000.0Hz (jitter RMS 0.0ns), CH14 frequency 2000.0Hz (jitter RMS 0.0ns).
    - Stream capture: `ok: true`, 178,816 bytes stored across 36 reads, CH8 frequency 1000.0Hz, CH14 frequency 2000.0Hz.
    - Clean session teardown confirmed.
