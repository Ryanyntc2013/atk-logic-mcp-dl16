# DL16-TASK-019 — session configuration and reproducible-build remediation

## Objective and scope

Repair proven request-parsing and patch-packaging defects following TASK-018.
Keep one-shot as the default. Do not change RX termination, FPGA sequencing,
USB recovery, trigger encoding, or the B6 retry based on an unproven hypothesis.
Evidence: TASK-018 archived metadata and console observations; source inspection;
native request-parser regression and fresh pinned-clone build.

## Failure analysis

1. **Confirmed configuration defect:** `CaptureConfig.enabled_channels` starts
   as `{0,1}`. The session parser appended the requested `{8,14}`. Archived
   `cap_1791641573277_8694/meta.json` records `[0,1,8,14]`. One-shot records only
   `[8,14]`. The former comparison therefore did not use identical configurations.
   This defect does not prove why the second session capture returned zero samples.
2. **Confirmed packaging defect:** the session header remained untracked in the
   ignored checkout. Plain `git diff` omitted it. `reset --hard` left the header
   behind, allowing local builds to succeed although a fresh checkout lacked it.
3. **Patch-generation mistakes:** staging session-modified main/tests before
   exporting a working-tree diff excluded those modifications; the resulting
   patch contained only the header. PowerShell content pipelines also changed
   encoding/line endings, and unchecked native exit codes allowed failures to
   appear successful. Those intermediate products were not accepted as validation.
4. **Confirmed earlier framing defect:** embedding pretty-printed capture JSON
   violates single-line JSONL framing. Preserve the TASK-018 compaction fix.
5. **Unresolved physical cause:** zero samples with Complete may involve device
   state, transfer boundaries, stale packets, or cropping. No recorded raw RX
   trace establishes which occurred. Do not describe early Complete as proven or
   extend draining merely to turn incomplete results into successes.

## Remediation

- `session::parse_channels` parses into a temporary vector and replaces the
  configuration only after successful validation. Duplicates/range/type errors
  fail without partially changing the destination. The CLI calls this same helper.
- Native regression parses an actual JSON `[8,14]` request against a default
  `CaptureConfig`, verifies exactly two requested channels, then verifies an
  invalid duplicate request leaves the validated configuration unchanged.
- The tracked session patch now includes main.cpp, session_protocol.h, and native
  tests. Use `git add -N` for a new patch-owned file, then Git's native
  `git diff --binary --output=...` against the staged base-patched pin. Do not stage
  session edits into the base index before export.
- Bootstrap removes only the known patch-owned untracked header before applying
  patches. Builds and runtime binaries stay in place; unrelated untracked files
  are not globally cleaned.
- Verification uses a **new clone**, not merely reset of the existing checkout.

## LHX reference review

Reviewed fixed revision `8d7c209c1e3b13923620bb34cec915291a749612`:

- [session.py](https://github.com/LHX369963/dl16-cli/blob/8d7c209c1e3b13923620bb34cec915291a749612/dl16_cli/session.py):
  session initializes once and invokes acquisition without reinitialization.
- [acquisition.py](https://github.com/LHX369963/dl16-cli/blob/8d7c209c1e3b13923620bb34cec915291a749612/dl16_cli/acquisition.py):
  ordinary acquisition collects requested channel byte depths, treats RLE
  completion separately, and performs a stop in final cleanup. Its delay/stop
  behavior differs from our native core.

These are source observations and useful experiment directions, not evidence
that this device requires that exact sequence. The cited snapshot has no resolved
public license; no source was copied or translated. No LHX-inspired USB reset,
endpoint clear, timing delay, stop sequence, or receive-policy change was applied.

## Verification and acceptance

- `powershell -ExecutionPolicy Bypass -File scripts/bootstrap-native.ps1`:
  **34/34 native tests passed**, including the actual channel-parser regression.
  Important: upstream suite includes `test_device_open_hardware`; on this machine
  it reported hardware open success. This build run was therefore not purely
  offline, though it performed no capture. Earlier descriptions of the whole
  upstream suite as synthetic-only were inaccurate.
- A new `git clone --no-local --no-checkout` of the pinned repository, checkout
  of `5fc47744c18c99f9ad0f554a965eb8cd1160c836`, ordered application of base and
  session patches, and fresh CMake configure/build with VS2022/v142 all succeeded.
  MSBuild emitted its standard temporary-directory warning; build exited zero.
- `.venv\Scripts\python.exe -m pytest -q`: **108 passed in 2.92s**.
- `.venv\Scripts\python.exe -m compileall -q src`: passed (exit zero).
- `git diff --check`: passed. `git apply --stat scripts/patches/atk-dl16-session.patch`
  confirms all three required files (CLI, new header, native tests) are retained.

## Next gate

Session HIL remains failed/unaccepted. First repeat the authorized configuration
check with exactly CH8/CH14 and verify emitted metadata reflects precisely those
channels. If a later repeat yields zero samples, stop immediately and preserve
full response plus bounded raw RX/message/count diagnostics before selecting a
device-lifecycle or drain change. Do not remove B6 retry or enable session by default.
