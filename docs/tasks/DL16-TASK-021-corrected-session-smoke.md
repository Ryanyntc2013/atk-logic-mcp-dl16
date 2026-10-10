# DL16-TASK-021 — corrected-channel two-request session smoke

## Objective and scope

Prepare a bounded, auditable session smoke using exactly CH8/CH14 following TASK-019 parser repair and TASK-020 evidence logging. Baseline: `d91936b899439b24cd03ccc063c6f4063d4d2dd5`.

The operator initially authorized offline preparation, then confirmed onsite PWM0 -> CH8 / PWM1 -> CH14 wiring and safety and authorized hardware connection on 2026-10-11. A bounded corrected-channel smoke is now authorized. Native `info` confirmed DL16 Plus / MCU v1.9 / FPGA v2.22 / USB 2.0; no competing ATK/Logic process was observed. Current signal frequency/state is not independently confirmed. The pinned CLI does not expose supported PWM configuration; this block will not invent raw vendor commands or use a different USB backend to set PWM. Capture validity and waveform quality remain separate.

No reset, endpoint clearing, native suite/bootstrap, firmware/driver change or remote push is performed. Existing uncommitted `docs/LOCAL-HANDOFF.md` is preserved outside the task commit.

## Plan and acceptance

- Default invocation is a dry run without starting a native worker.
- Live execution requires explicit current device/wiring/voltage confirmations and declaration that the safe signal source is already configured.
- Fixed capture configuration: channels `[8,14]`, 20 MHz, 10 ms, threshold 1.6 V, immediate trigger; expected 200,000 samples per channel.
- Use exactly one owned session, at most two capture requests, with durable TASK-020 journal and unique non-overwriting step records.
- Reject incorrect channels, incomplete counts, missing ACK/Complete/integrity or ambiguous metadata. Stop before request two on first failure. Never replay or fallback.
- Close the owned session on every exit and preserve cleanup/evidence failures. Do not configure PWM or manipulate other processes/devices.
- Test dry run, explicit gates, two valid mocked results, first-failure stop, metadata mismatch and cleanup entirely offline.

## Evidence authority

Requests and source descriptions are operator declarations. Responses and saved capture metadata are native-reported evidence. Exact counts and completion fields prove only capture validity against this test's criteria, not waveform quality, calibrated timing, external gating or physical provenance. Even a passing two-request smoke is not full persistent-session acceptance; a separately bounded repeatability block and waveform validation remain required.

Use fresh local task evidence directories; retain original records and hashes, share only redacted summaries. No raw customer waveform, serial or personal paths are committed. Source provenance remains [SOURCES](../SOURCES.md); no LHX implementation is copied.

## Verification and next gate

## Execution and evidence — 2026-10-11

Offline validation: `.venv\Scripts\python.exe -m pytest -q` — **134 passed in 5.21s**; `.venv\Scripts\python.exe -m compileall -q src scripts` and `git diff --check` passed.

Live command (operator had confirmed connection/wiring/safety):

```powershell
.\.venv\Scripts\python.exe scripts\dl16_session_smoke.py --taskdir artifacts\hil\DL16-TASK-021 --live --confirm-connected --confirm-wiring --confirm-voltage --confirm-signal-configured --source-declaration "Operator confirmed connected safe CH8/CH14 wiring; signal state unverified; no PWM configured by this block"
```

Result: **HIL_FAIL / SECOND_REQUEST_FAILED**, expected nonzero harness exit. Native PID `33008`; binary SHA-256 `631930e868e52de2361d8fada89d6eecc40f44a2896cde96320ac06ad860b78e`.

- Request `p33008-2`: COMPLETE, ACK and Complete present, exact metadata channels `[8,14]`, 200,000 samples/channel, elapsed about 0.437 s.
- Request `p33008-3`: INCOMPLETE_CAPTURE, Complete present, both requested channels received 0/200,000 samples, elapsed about 0.110 s. No third request, replay or fallback. Session close completed.
- The second response names an artifact directory but it was absent on disk; the harness preserved the full response and reported missing metadata rather than inventing it.
- Separate postflight native `info` failed: `Invalid MCU version header`, 512-byte all-zero preview. No retry/reset/endpoint clear was attempted. This is a new observed postflight error, not proven firmware damage or a diagnosed causal link.
- No PWM configuration was issued; current waveform/source state was not measured. No waveform pass or calibrated timing claim.

Original evidence: ignored `artifacts/hil/DL16-TASK-021/`, including unique run `smoke-20261010-164722-77e2460e4c6d43cf8742929b16c05c1b`, durable step files, full session journal, console/test/status logs and SHA256 manifest. Preflight identification is explicitly labelled as transcribed from tool output; do not describe it as a saved original native stdout trace.

**Outcome:** harness delivery DONE; corrected-channel persistent capture acceptance FAILED. The TASK-019 channel fix does not resolve the observed zero-sample second capture. Physical cause remains unknown because this journal is not raw USB RX evidence. Keep one-shot default and B6 retry.

**Next task: DL16-TASK-022** — bounded native RX/message/count/crop diagnostics with offline regressions before another controlled hardware block. Distinguish stale messages, transfer boundaries and crop losses using recorded evidence; do not assume premature Complete or add draining/reset to force a pass. Device readiness must be freshly established before new captures.
