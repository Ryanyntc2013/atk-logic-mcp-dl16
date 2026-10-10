# DL16-TASK-001 — initial local validation

Status: `NEEDS_HUMAN_HIL`; offline suite is available, no physical DL16 tested here.

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

