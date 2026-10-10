# DL16-TASK-002 — cross-implementation protocol consistency and local HIL gates

**Owner:** local Codex/Cursor agent on Windows.  
**State at issue:** READY_FOR_OFFLINE_WORK / HIL_REQUIRES_SITE.  
**Depends on:** `DL16-TASK-001` for first verified physical connection/capture. **Do not imply TASK-001 is complete merely because Windows cloud CI compiled CPP.**

## Mission

Turn the pinned four-source review [LHX cross-validation report](../research/LHX369963-dl16-cli-cross-validation-2026-10-10.md) into reproducible **byte-level regression tests**, high-confidence compatibility fixes and a controlled hardware validation record on the owner's DL16. Keep the existing C++/WinUSB backend authoritative for normal Windows MCP operation until replacement/patch is justified by evidence.

**No protocol/capability modifications solely from report assertions; report disagreements explicitly.**

## Operating authority

- May autonomously inspect pinned upstream sources, implement **offline** test vectors, refactor deterministic pure functions, build/test on local Windows, record sanitized evidence, and commit small changes to this repository.
- May perform read-only status or bounded capture on already-verified, user-confirmed signal wiring and thresholds when user has declared device available, consistent with `AGENTS.md` and `docs/HIL-TEST-PLAN.md`.
- **Must request approval** before changing USB driver, automatic USB bus reset / power-cycle, firmware/FPGA, raw undocumented command, unknown wiring, unknown output level, or enabling experimental 9B/10B trigger frame variant on live device.
- Do not copy code from LHX: no explicit license was located in its publicly checked tree. Use report, own code and independently constructed test vectors; preserve provenance.
- Never run vendor GUI and native MCP hardware access concurrently.

## Phase A — reproducible offline analysis (proceed without hardware)

1. Record clean baseline: `git status --short`, `git rev-parse HEAD`, OS, Python, MSVC/CMake; record actual upstream native commit fetched by the bootstrap. Confirm `external/` is gitignored.
2. Run existing tests: `python -m pytest -q`; `python -m compileall -q src`; `powershell -File scripts/bootstrap-native.ps1`; `external/ATK-Logic-Mcp/build/Release/atkdl16_tests.exe` on Windows (or equivalent).
3. Create explicit protocol discrepancy matrix from the research report, with one `AGREE / DIFF / UNKNOWN` entry per test, and link exact code path and sample vector.
4. Implement reproducible offline tests (can use hand-authored vectors) for:
   - CRC (empty `FFFFFFFF`; `123456789` `D202D277`) and exact little-endian transport placement.
   - 2048-byte FFCC inverse TX/RX bank transform and segmented bulk packets; 512B handshake must **not** be passed to 2048B bank conversion.
   - 13B parameter body for common rates 20/100/250MHz, buffer/RLE flags, signed thresholds and uint40 sample depths.
   - Nibble mapping, 9B official/CPP simple trigger versus 10B LHX/HUGEL variants; assert differences and annotate source-version provenance rather than choosing one implicitly.
   - RX packet fragmentation, order1/3/4/5/6, missing/duplicate ACK/complete, per-channel sample counts and RLE overflow.
   - Buffer/stream tail removal, boundary samples, trigger-offset crop and matching reference/target sample start.
5. If current CPP source is only under ignored `external/`, do **not** commit untracked edits there. For actual patch, choose a reviewed fork pin or applied patch tracked in this repository with a SHA/hash and CI build.
6. Add tests to CI **without** requiring connected hardware, and report test counts and failures honestly.

**Phase A acceptance:** deterministic vectors documented in a new `tests/` module and CI passes on Windows and Python jobs; unresolved differences remain explicitly labeled. No silent changes to sample-rate mapping, 9/10B frame or device whitelist.

## Phase B — compatible live-device matrix (only when TASK-001 succeeds and operator approves)

Record physical model and firmware version, VID/PID, USB speed, Windows driver, C++ commit, host app version, actual signal source, GND, threshold, channel and cables.

| Gate | Method / input | Required evidence |
|---|---|---|
| B0 model and handshakes | connect known DL16, status/query; no reset by default | MCU/FPGA version, raw response lengths (including any 512B), errors/retries |
| B1 sample indices | known 1kHz loopback, use supported 20/40/100/250MHz; inspect sample period | code/index, actual frequency, expected samples per period; **25/500 only if approved and spec-supported** |
| B2 instant capture | 1kHz known signal plus static-low control, bounded 1/2 channels | per-channel exact `requested/actual` count, ACK, complete, raw sizes and SHA-256 |
| B3 rising/falling gates | controlled stable no-edge interval, delayed edge, 50% trigger position | whether edge **really gates** capture; trigger index, 9/10B difference only with explicit authorization |
| B4 receive/tail/crop | cross compare raw USB data, order-3, raw channel bytes, cropped channel data | equal-length valid sample count, correct first/last sample, pre-trigger align |
| B5 common-source skew | split one pulse into CH3 and CH7, known leads/scope | signed lag distribution, missing/extra pulses, input chain uncertainty; no 1us certification from sample interval |
| B6 repeat reliability | bounded 30 captures (model-appropriate rate/depth) | count successful, failures, reconnect behavior; no auto reset or driver change |

For each gate, keep vendor GUI **separate** from MCP ownership of the USB interface. A reported order-4 ACK and order-6 complete do **not** prove edge-trigger correctness.

**Phase B acceptance:** saved raw material plus reproducible summary, not merely a CLI exit code. Mark `HIL_NOT_RUN` for any gate without local instrument.

## Phase C — implement only proven corrections

- File concrete `issue/PR` or a task-numbered patch for each confirmed mismatch; include original bytes, failure reproduction and regression tests.
- If model-dependent sample-rate table varies, expose an explicit **model/firmware profile**; never silently fall back to 20 MHz for unknown rates.
- If 9B and 10B are both valid, select using evidence-backed profile, not a global hardcoded switch.
- Preserve source and trimmed data, immutable input hashes and per-channel sample indices when fixing order-3/tail behavior.
- Defer RLE, PWM loopback, persistent session, streaming and multiple protocol decoders to follow-up tasks unless small isolated improvements are test-covered and authorized.

## Required evidence bundle

Create the following **locally** (ignored, not in Git) after each HIL experiment:

```text
artifacts/hil/DL16-TASK-002/
  RESULT.md                # gate matrix, PASS/FAIL/NOT_RUN, conclusions
  environment.json         # OS, device/firmware, build/pin, wire setup, version
  offline-tests.txt        # exact command and terminal exit/results
  native-build.txt         # exact MSVC/CMake command/log
  raw/                     # optional permitted USBPcap/wire.bin recordings
  captures/                # per-channel waveform and metadata
  SHA256SUMS.txt            # hashes of retained evidence
```

Do **not** commit raw customer traffic, serial numbers, personal paths, secrets or large hardware captures. Commit sanitized report or issue/PR with local evidence hashes/path references, and keep the working tree clean.

**Agent handoff report template:**

```text
Task: DL16-TASK-002
State: DONE | BLOCKED | NEEDS_HUMAN_HIL
BaseCommit: <sha>
ResultCommit: <sha or none>
Baseline: <OS, VS2022, Python, native source pin>
Offline: <command, pass/fail counts and CI URLs>
HIL: HIL_PASS | HIL_FAIL | HIL_NOT_RUN, per-gate B0..B6
Consistency: <R1..R5 AGREE/DIFF/UNKNOWN with evidence links>
Evidence: <local paths, SHA256, no raw data committed>
Changes: <what changed, and justification>
Risks: <known incompatibilities; what was not checked>
Next: <single suggested DL16-TASK-003 scope>
```

## Phase A status (2026-10-10, offline)

Phase A is implemented and passing offline. Independent reference codec:
`tests/protocol_reference.py`; versioned vectors: `tests/test_protocol_vectors.py`
(38 tests) plus a hash-locked `tests/vectors/dl16_protocol_vectors.json` and an
optional native harness (`scripts/build-vector-harness.ps1`) that proves the pinned
C++ backend matches the reference byte-for-byte (frames and RX parsing). Full Python
suite: **55 passed**. Discrepancy matrix and preserved divergences:
`docs/research/DL16-TASK-002-phase-a-protocol-vectors.md`.

- CRC, TX framing, 2048B bank transform, trigger nibble, parameter payload, RX
  reassembly and RLE/tail vectors **AGREE** across documented sources.
- 9B/10B trigger payload and 25/500 MHz index conflicts are **DIFF** and kept as
  separate tables; nothing was silently merged.
- Trigger gating / physical alignment remains **UNKNOWN / HIL_NOT_RUN** (Phase B).
- No live backend behavior changed by this phase.

## Local invocation prompt (paste into Codex/Cursor)

> Read `AGENTS.md`, `docs/tasks/DL16-TASK-002.md`, `docs/research/LHX369963-dl16-cli-cross-validation-2026-10-10.md`, `docs/HIL-TEST-PLAN.md`, and the current source/test tree. Execute Phase A autonomously with clean, numbered commits and objective evidence. Confirm what is already done for DL16-TASK-001; if hardware is unavailable or unverified, do **not** attempt live captures or driver/reset changes. After offline acceptance, pause at the explicit hardware gate and return the required report. Do not silently merge conflicting sample indices or 9/10-byte trigger formats. Clearly separate source review, synthetic tests and locally reproduced HIL.
