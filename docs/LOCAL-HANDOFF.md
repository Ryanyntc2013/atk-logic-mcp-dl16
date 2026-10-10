# DL16-TASK-001 — initial local validation

Status: `NEEDS_HUMAN_HIL`; offline suite is available, no physical DL16 tested here.

**Objective:** validate pinned C++ backend with your specific DL16, establish working MCP in local Codex/Cursor and a correct hardware evidence baseline.

**Allowed without additional authorization:** clone/update only the pinned `external/` references; install a project-local Python venv; compile C++ and run offline tests; read already saved capture files; check USB enumeration when DL16 is connected; issue bounded captures using operator-confirmed wiring/threshold within device ratings; improve code/tests and commit cleanly. These operations must not alter firmware or drivers.

**Requires human approval:** flash/update MCU/FPGA, send firmware/bootloader/raw commands, physically alter probes or unknown pin connections, install/replace WinUSB drivers, forcibly reset or power cycle USB devices.

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
