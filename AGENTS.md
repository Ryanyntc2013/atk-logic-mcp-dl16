# AGENTS.md — ATK-DL16 MCP development contract

This file is binding guidance for Codex/Cursor/other coding agents in this repository.

## Mission
Build a stable, auditable MCP bridge for ALIENTEK DL16/DL16 Plus, combining the pinned native USB/FPGA capture core, reliable offline artifacts, deterministic timing analysis, and optional protocol decoders. **Hardware behavior is unverified until evidence is recorded.**

## Roles and execution rights
- **Cloud planning/review**: architecture, acceptance criteria, safety boundary, technical audit, next task ID.
- **Local coding Agent**: may autonomously modify source, add tests, compile, lint, run synthetic/golden tests, and commit small audited changes.
- **Hardware operations**: only when the user explicitly states the DL16 is connected and gives the signal/channels/voltage context. Low-risk read-only/status and bounded capture permitted then; never change unknown physical wiring. Firmware flash, bootloader, raw MCU command, firmware update, power cycling, or driver replacement require explicit human approval.
- **Never use send_raw, arbitrary vendor commands or firmware-upgrade opcodes 0x80/0x82/0x83/0x84/0x85/0x86.**

## Task protocol
1. Each task receives a unique ID: `DL16-TASK-###` (never reuse an ID).
2. Record task objective, allowed scope, implementation plan, acceptance tests and evidence location.
3. When successful, run tests, record exact commands and output, keep the worktree clean, commit with the task ID in message.
4. Handoff response MUST say: `DONE`, `BLOCKED`, or `NEEDS_HUMAN_HIL`, with commit hash, tests, changes, known risks, and next task suggestion.
5. If hardware is absent, complete all offline work and return `HIL_NOT_RUN` rather than manufacturing or relabeling data.

## Engineering invariants
- Code under `src/dl16_mcp` must remain import-safe without USB. Live capture goes only via `backend.py` and the pinned native CLI.
- No extra DLL injection, USB driver installation, or WinUSB changes automatically.
- Keep the ATK-Logic GUI closed during MCP-owned USB sessions. Do not auto-kill processes.
- Prefer Windows 10/11 + VS2022 + Python 3.12 for live verification. Linux offline tests supported.
- Time units: externally nanoseconds, sampling explicitly in Hz; in files save original sample indices; edge indices follow LSB-first order.
- Clamp displays to bounded outputs; do not return multi-MB waveforms inside MCP tool messages.
- Never silently reclassify incomplete/unknown/synthetic data as `REAL_HARDWARE` or `HIL_PASS`.
- Treat a metadata field labeled REAL_HARDWARE as a statement by the data source, not cryptographic proof.
- `PASS_WAVEFORM` means the waveform passed the numeric criterion, NOT calibrated instrument or end-to-end physical synchronization certification.
- Trigger ACK proves firmware acknowledged a command, not that an external trigger truly gated acquisition.
- For <1us measurement do not claim uncertainty below sample interval without independent calibration.
- Use synthetic, golden archived, contract-mock, and genuine physical HIL as separate evidence tiers.
- RLE, stream, multi-device acquisition and complex triggers remain future extensions until verified.

## Folder ownership
- `src/dl16_mcp/backend.py`: isolated native executable adapter.
- `src/dl16_mcp/artifacts.py`: artifacts, provenance and offline vendor .atkdl reading.
- `src/dl16_mcp/analysis.py`: independent timing math; deterministic offline tests required.
- `src/dl16_mcp/server.py`: MCP protocol thin layer; no USB logic here.
- `external/`: ignored pinned upstream checkouts; do not blindly vendor GPL sources or proprietary DLLs.
- `docs/HIL-TEST-PLAN.md`: physical acceptance gates.

## Required test commands
`python -m pytest -q`; `python -m compileall -q src`.
Native optional: `powershell -File scripts/bootstrap-native.ps1` then native `atkdl16_tests.exe`.
Never mark HIL validated from GitHub Actions alone: cloud CI has no DL16 attached.

## First local mission
Execute `DL16-TASK-001` in `docs/LOCAL-HANDOFF.md`. Preserve original report when modifying it; write findings to `artifacts/hil/` (ignored) and a redacted issue or PR summary.
