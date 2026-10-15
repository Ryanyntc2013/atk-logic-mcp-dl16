# DL16-TASK-066 — Buffer raw-bank carry and USB-free CLI help

**Owner:** local Executor for TS3-DL16FIX-20261015.
**State:** CODE_READY; independent review pending; HIL_NOT_RUN.
**Base:** 7e27c2342dcb060426171ec753ff43fb8f96091c.
**Native pin:** 5fc47744c18c99f9ad0f554a965eb8cd1160c836.

## Objective and authority

Fix Buffer loss of raw USB read tails and make `--help` / `-h` return before command dispatch. User authorizes isolated source edits, offline builds/tests and a commit on `fix/DL16-TASK-066-buffer-residue-help`. No push, hardware actions, main-worktree bootstrap/build, bench binary replacement, wire protocol/lifecycle changes, B6 handshake repair or timeout recovery changes.

## Implementation

The new last patch `scripts/patches/atk-dl16-buffer-residue.patch` adds a per-capture `RawBankAccumulator`. All positive read bytes enter it after raw logging, including lengths preserved by transport timeout handling. Only complete 2048-byte banks are converted; 0..2047 bytes remain for the next read. Every return records `raw_bank_residue_bytes`; nonzero terminal residue makes the result INCOMPLETE without padding or adding samples. JSON results and saved metadata expose the count, even with diagnostics disabled. Existing primary error codes/messages survive terminal marking.

A tested outer CLI entry function scans every argument for help before dispatch, including list/info/session/capture/inspect/capabilities. It prints usage and returns zero without enumerating/opening devices or starting the session. Unknown/missing capture and inspect flags, invalid capture mode/trigger and unexpected list/info/capabilities arguments are rejected. Omitted trigger retains its existing wire behavior; usage now describes the legacy default accurately.

Native tests default to offline and skip `test_device_open_hardware`; hardware opt-in remains a separately authorized `--hardware` invocation. No such invocation occurred here. The bootstrap removes only the new patch-owned untracked CLI header before reapplying the last patch.

## Plan, commands and acceptance

1. Local clone with `git clone --no-hardlinks E:/code/atk-logic-mcp-dl16/external/ATK-Logic-Mcp E:/code/dl16-task-066/external/ATK-Logic-Mcp`. Its origin is the local source, so bootstrap fetches require no network.
2. Apply the existing stack with `powershell -NoProfile -File scripts/bootstrap-native.ps1 -SkipBuild -SkipTests`. Extract legacy behavior into test seams and record expected failures using native `--offline --filter test_buffer_` and `--offline --filter test_cli_help_`.
3. Implement and generate the new patch. Configure using VS2022 Community at `D:/Program Files/Microsoft Visual Studio/2022/Community`, then replay the complete stack with `powershell -NoProfile -File scripts/bootstrap-native.ps1 -Toolset auto` in this worktree only.
4. Native acceptance: 41/41 tests PASS, one explicit hardware test skipped. Eight new tests cover 14,848-byte reads, zero-byte timeouts, all 4,097 two-way splits of two banks, one-byte reads, all terminal residues 1..2047, ordered ACK/Offset/ChannelData/Progress/Complete, terminal failure serialization/error preservation, and 56 help argument/command combinations with zero dispatch calls.
5. Run offline pytest with the main repository's `.venv/Scripts/python.exe` as interpreter, worktree cwd/config/source. Add one mock backend regression proving residue errors remain INCOMPLETE without retry. Temporarily hold aside only this worktree's new CLI during the final full suite, restoring it in `finally`, because existing optional tests invoke non-help CLI commands. Run `python -m compileall -q src`.
6. Independent review remains pending. Physical operation and LEADCAP timeout causality remain UNVERIFIED.

## Evidence and execution deviation

Evidence is in `E:/code/timeSync3/artifacts/TS3-DL16FIX-20261015/`: commands, raw stdout/stderr, exit JSON, pre-fix extraction, preparation scripts, result.json and SUMMARY.md. No commit is made in timeSync3.

Both pre-fix regressions failed with exit 1: fragmented output mismatched whole-bank output; help dispatched to a counter stub returning 99. After correction the full stack reapplied and built successfully with MSVC 19.36.32537.0.

The initial Python suite ran after the CLI was built: 234 passed, 75 skipped. Sixteen existing tests invoked the new CLI (one capabilities query, seven invalid capture argv checks, and eight session processes with hello/invalid requests/close). These code paths reject before device open and performed no hardware action, but the invocations violated this task's stricter help-only CLI execution restriction. This deviation is disclosed, not erased by later passes. The final suite holds the CLI aside so those optional tests skip: 219 passed, 91 skipped; exact reasons are retained in pytest-final.stdout. No live capture/status/info or analyzer/serial tool was run.

## Known risks and next task

HIL_NOT_RUN: offline tests establish reconstruction and dispatch behavior only. They do not prove that fragmentation caused the historical LEADCAP timeout or that short firmware replies always belong to a continuous bank stream. Existing handshake, lifecycle and cleanup telemetry issues remain. Optional native Python harnesses and absent archived HIL inputs remain explicit skips. Request an independent review of TASK-066 before any separate hardware-validation authorization.
