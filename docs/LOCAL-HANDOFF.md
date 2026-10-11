# Current resume ? 2026-10-11, after TASK-034

Latest implementation before TASK-033/034 delivery: 3f7a8f2 (TASK-032). Current changes add public guarded logic_pwm and logic_session_close, CLI parity, PWM hello capability guard and real MCP stdio acceptance. 155 Python tests passed; current patched binary and raw evidence retained under ignored artifacts/hil/DL16-TASK-032/evidence and TASK-034.

Operational default stays one-shot/B6. Opt-in buffer session requires DL16_BACKEND_MODE=session and DL16_EXPERIMENTAL_SESSION_LIFECYCLE=depth-stop-v1 plus current patched DL16_CLI_PATH. Session status device info is cached. Native capture failure closes/invalidates owner; later explicit operation creates fresh worker without replay. Same-owner dual PWM20/20 dynamic captures passed; real MCP setup/capture/measure/close passed and fresh postflight info ready. Calibration,stream/RLE,all trigger/model profiles and unplug are not accepted.

TASK-034 public PWM requires explicit confirm_safe_wiring and output/rate/duty validation;native hello must advertise pwm. Close stops owned outputs,cleanup errors surfaced. Standalone CLI exit closes owned outputs; use persistent MCP for source setup and capture.

No remote push/new CI claim. Next: extend session reliability/mixed-generation tests, then Stream/cancel and RLE under separate offline/HIL gates. B5 same-source split and calibrated scope require operator setup beyond current independent PWM wiring.

The original operator-provided handoff below is preserved as historical evidence and superseded for CURRENT software status only.

---

# Current local handoff — 2026-10-10, after DL16-TASK-019

## Resume here

- **Software remediation: DONE. Session hardware acceptance: FAILED / revalidation pending.**
- Implementation baseline: `53400b28d7eafbcae8d691456f43ca1cd48e85c6` (`53400b2`).
- Branch: `main`; worktree was clean before this handoff update.
- Remote `main` was verified by HTTPS `git ls-remote` as
  `232a5467d4148de52ce8f95220b44079d5046e48` on this handoff date. TASK-018 implementation,
  its fixes/HIL report, and TASK-019 are local commits not yet pushed. Remote tracking refs
  may be stale because SSH authentication fails; HTTPS push worked previously.
- Default operational backend remains **one-shot**. `DL16_BACKEND_MODE=session` is opt-in
  experimental capture functionality. Do not enable it by default or remove the B6 retry.

## Environment and confirmed wiring

- Workspace: `E:\code\atk-logic-mcp-dl16`; Python in `.venv` (3.12).
- Windows + VS2022 Community; native build uses installed v142 with libusb DLL import library.
- Native upstream pin: `gjjisadog/ATK-Logic-Mcp@5fc47744c18c99f9ad0f554a965eb8cd1160c836`.
- Last observed device: DL16 Plus, MCU v1.9, FPGA v2.22, USB 2.0, VID:PID `1A86:FFCC`,
  USB port 7. This is a single-device/firmware baseline, not universal compatibility.
- Operator confirmed **PWM0 -> CH8, PWM1 -> CH14**, safe wiring and device connection.
  Do not request CH0 rewiring or assume PWM0->CH0. Prior diagnostic configuration used
  PWM0=100 Hz, PWM1=1007 Hz, both 50% duty; CH8+CH14, 20 MHz, 10 ms, threshold 1.6 V,
  immediate trigger. PWM outputs were stopped after the last HIL blocks.
- Last explicit status after TASK-018 HIL: connected/ready. TASK-019's native suite also
  successfully opened the device. Neither observation guarantees current readiness.
- Before further HIL, check current GUI/process/USB ownership and ready state. No auto-kill,
  USB reset, endpoint clear, driver replacement, firmware or raw vendor commands.

## Implemented capabilities

- Nine MCP tools: status, capture, inspect, measure_skew, measure_pwm, export, filter,
  search, decode. Offline UART/I2C/SPI decoding and bounded disk-based artifacts.
- One-shot capture supports trigger gating, trigger position, multi-condition triggers,
  and trigger timeout through tracked native patches. Default capture channel cap is four;
  larger requests require the operator's explicit `DL16_MAX_CHANNELS` setting.
- B6 workaround: narrow FPGA device-info open-error retry, at most three total attempts,
  0.5/1.0-second backoff, observable attempts/retry_log. Timeout/incomplete capture results
  are not retried. This is mitigation, not a demonstrated root-cause fix.
- Persistent native JSONL worker and Python child owner exist. Serial requests, request IDs,
  bounded framing, shutdown/timeout handling and no automatic capture replay/fallback are
  tested. Cached session status is not a fresh live FPGA query.

## TASK-018 HIL observations and corrections

1. A second native session was refused with `DEVICE_OPEN_FAILED` and port-claimed text.
   Ownership exclusion worked in that probe; it was not returned as a typed `DEVICE_BUSY`.
2. Initial capture completed on-device but its nested pretty-printed JSON broke JSONL
   framing. TASK-018 added JSON-aware compaction and bounded protocol diagnostics.
3. After framing repair, a persistent sequence had one successful capture followed by
   `INCOMPLETE_CAPTURE`: Complete arrived but enabled channels had 0/200000 samples.
   The block stopped at run 2; no session replay. Acceptance was **not** 20/20.
4. Separate one-shot block: 20/20 final COMPLETE. Sixteen calls used the visible B6 retry;
   four were first-attempt successes. Twenty-one one-shot artifacts include a smoke capture.
5. **TASK-019 discovered the configurations were NOT equivalent:** session parsing appended
   CH8/CH14 to default CH0/CH1. Archived session metadata lists `[0,1,8,14]`; one-shot lists
   `[8,14]`. Withdraw any claim of identical-configuration causal comparison. The zero-sample
   failure remains observed, but its physical cause is still unknown.
6. Data is under ignored `artifacts/hil/DL16-TASK-018/`, including a SHA256 manifest and
   retained original artifacts. Some response/timing records were transcribed from console;
   do not claim a complete saved raw-RX trace or immutable per-request response journal.

## TASK-019 remediation completed

- `session::parse_channels` now validates into a temporary vector and atomically replaces
  defaults. Native regression uses the same helper as the CLI, parses `[8,14]`, asserts exact
  channel identity, and checks an invalid duplicate request leaves prior config intact.
- Session patch previously omitted untracked `session_protocol.h`; local leftover files
  masked fresh-checkout failure. Some attempted patch exports also staged main/tests too
  early, producing header-only patches. The committed patch now includes **all three**:
  `cli/main.cpp`, new `cli/session_protocol.h`, and `tests/unit/test_main.cpp`.
- Patch export uses Git's `diff --binary --output` against the staged **base-only** patched
  pin, with `git add -N` for new session files. Do not stage session edits into that base
  index before exporting the working-tree diff. Do not use PowerShell content redirection
  to generate patch bytes.
- Bootstrap resets the ignored checkout and removes only the known patch-owned untracked
  header before applying base then session patches. Avoid blanket cleanup of user files.
- Fresh `git clone --no-local --no-checkout` at the pin, ordered application of both tracked
  patches, and a fresh VS2022/v142 CMake build succeeded; no leftover header was needed.

## Latest verification

- `.venv\Scripts\python.exe -m pytest -q`: **108 passed in 2.92s**.
- `.venv\Scripts\python.exe -m compileall -q src`: passed.
- `powershell -ExecutionPolicy Bypass -File scripts/bootstrap-native.ps1`: **34/34** native
  tests passed, including actual channel-parser regression.
- Important: upstream suite contains `test_device_open_hardware`; it opened the connected
  device in this run. Do not describe the entire native suite as purely offline. TASK-019
  performed no PWM start or capture. Corrected-channel capture HIL: **HIL_NOT_RUN**.
- Fresh pinned-clone build, JSONL hello/invalid-capture/close smoke (no USB open), and
  `git diff --check` passed.
- The earlier Python/native GitHub workflows passed for `71ca377`. That does not cover the
  current session implementation or TASK-019; new remote CI has not yet been run for these.

## LHX reference and evidence limits

Reviewed `LHX369963/dl16-cli@8d7c209c1e3b13923620bb34cec915291a749612`, particularly
`session.py` and `acquisition.py`: initialize once, avoid per-capture reinitialization,
collect ordinary channel data by expected byte depth, and stop in cleanup. These differ
from our native core and are useful diagnostic hypotheses. They do not establish the cause
of this instrument's zero-sample result. No LHX source was copied/translated (license
unresolved); no USB reset, stop/timing or drain-policy change was adopted from it.

## Next work, in order

1. Review `docs/tasks/DL16-TASK-019-session-remediation.md`, TASK-018 design and mandatory
   TASK-002/LHX cross-validation references. Confirm actual built CLI matches current patches.
2. Before new HIL, make the harness persist complete request/response JSON, native PID,
   effective channels, native binary hash, elapsed time and cleanup outcomes as each step
   runs. Do not reconstruct a new acceptance record from console output alone.
3. Under the confirmed wiring and scoped operator authorization, perform one corrected
   CH8/CH14 session smoke; verify metadata channels are exactly `[8,14]`. Then test a second
   capture in the same session. Stop on first incomplete/error and preserve diagnostics.
4. If still zero samples, investigate bounded raw-RX/message/count/crop diagnostics. Do not
   assume premature Complete or add draining/FPGA reset simply to make tests pass. If first
   two corrected requests pass, proceed to a separately bounded repeatability block.
5. Keep one-shot default and B6 retry until corrected session HIL is accepted. B5 common-source
   skew still needs a shared split signal; current two PWM outputs are not that setup.
6. Push local commits and check fresh native/Python CI only when asked to push. No HIL claim
   can be established by cloud CI.

### Key files

- `scripts/bootstrap-native.ps1`, `scripts/patches/atk-dl16-local-build.patch`,
  `scripts/patches/atk-dl16-session.patch`: reproducible native patch/build boundary.
- `src/dl16_mcp/backend.py`, `src/dl16_mcp/session.py`: one-shot retry and session process owner.
- `tests/test_backend.py`, `tests/test_session.py`: Python contracts; native regression lives
  inside the tracked session patch.
- `docs/HIL-PHASE-B-STATUS.md`: hardware findings; `docs/tasks/DL16-TASK-018-persistent-session-design.md`
  and `docs/tasks/DL16-TASK-019-session-remediation.md`: design/remediation/acceptance status.
- `scripts/hil-evidence.ps1`: evidence manifest, offline by default.

---

# Historical DL16-TASK-001 — initial local validation

Historical status at task creation: `NEEDS_HUMAN_HIL`; this is not the current project status.
Use the handoff above and `HIL-PHASE-B-STATUS.md` for subsequent local hardware observations.

**Objective:** validate pinned C++ backend with your specific DL16, establish working MCP in local Codex/Cursor and a correct hardware evidence baseline.

**Allowed without additional authorization:** clone/update only the pinned `external/` references; install a project-local Python venv; compile C++ and run offline tests; read already saved capture files; check USB enumeration when DL16 is connected; issue bounded captures using operator-confirmed wiring/threshold within device ratings; improve code/tests and commit cleanly. These operations must not alter firmware or drivers.

**Requires human approval:** flash/update MCU/FPGA, send firmware/bootloader/raw commands, physically alter probes or unknown pin connections, install/replace WinUSB drivers, forcibly reset or power cycle USB devices.

**Build/toolset note (DL16-TASK-003):** `scripts/bootstrap-native.ps1` defaults `-Toolset` to the locally installed VS2019 compiler (`v142`) and falls back to the machine default (`v143`) when it is not installed. Because the pinned upstream's bundled libusb static library was compiled with a newer MSVC (front-end 19.39+) and older local toolsets cannot link it (`LINK : fatal error C1900`), the script links the libusb **DLL import library** and stages `libusb-1.0.dll` next to the executables. The pinned checkout content is never modified. Use `-Toolset v143` (or `-Toolset auto`) to override.

## Work plan

1. `git status --short` and `git rev-parse HEAD` => record task baseline.
2. `powershell -ExecutionPolicy Bypass -File .\scripts\setup-windows.ps1` => Python + C++ native build and tests.
3. `dl16ctl status` => identify model, firmware, USB speed or record failure code.
4. Run a known 1kHz PWM from a safe verified signal source: 10MHz/100ms CH0 first, then CH0+CH1; save full CLI JSON and SHA-256 of files.
5. Confirm ACK, completion, all channels' sample counts and bit patterns. Compare official GUI separately.
6. Verify `logic_measure_skew` on a split same-source signal to CH3 and CH7. Only test wireless master/slave when scope confirms wiring and output.
7. Complete gates 0 and 1 of `docs/HIL-TEST-PLAN.md`. If gate 0 fails, do not run other hardware stages.
8. Produce `artifacts/hil/DL16-TASK-001/RESULT.md` (ignored), sanitized GitHub issue or PR summary, next `DL16-TASK-002` proposal.

## Local Agent handoff output (required)

```
Task: DL16-TASK-001
State: DONE | BLOCKED | NEEDS_HUMAN_HIL
Commit: <full_sha>
Environment: <OS, Python, compiler, DL16 model and firmware>
Offline tests: <command, pass count>
Native tests: <command, pass count>
Physical HIL: HIL_PASS | HIL_FAIL | HIL_NOT_RUN
Evidence: <paths + SHA256; no secrets>
Findings: <reproducible results>
Known risks: <list>
Next task: DL16-TASK-002 <one concrete scope>
```

Do not conflate code compiled, native CLI detected, hardware capture succeeded, trigger gated, and <=1us end-to-end accuracy. They are distinct gates.

## Next task already prepared

After this task's physical gate-0/1 evidence (or in parallel for **offline-only** work), the next distinct task is [DL16-TASK-002](tasks/DL16-TASK-002.md). Its underlying independent protocol evidence is [LHX cross-validation](research/LHX369963-dl16-cli-cross-validation-2026-10-10.md). Do **not** mark this initial HIL task complete just because cloud Windows/MSVC CI compiled the backend; skip `DL16-TASK-002` live phases until a safe physical device baseline is confirmed. Agent must not silently alter sample-rate index maps or 9B/10B trigger encoding based on third-party reports.

