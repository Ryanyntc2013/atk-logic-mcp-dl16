# DL16-TASK-046 — bounded offline raw-RX replay

Date: 2026-10-11. State: **DONE / HIL_NOT_RUN**.
Base commit: `138fbdc0eaa155a698dcdb2bef988b20b06e6efb`.
Result commit: **none**, explicitly requested; changes remain uncommitted.
The unfinished draft previously mentioned TASK-038; this completion uses the new
TASK-046 identifier and does not claim TASK-038 hardware acceptance.

## Objective, allowed scope and plan

Finish the existing USB-free `tests/native/raw_rx_replay.cpp` draft, its CMake
target and `tests/test_raw_rx_replay.py`. Enforce bounded input/feed/output,
reject malformed CLI and unknown unaligned raw bank tails, retain unknown
provenance and capture completeness, and exercise the actual executable.
Read AGENTS.md, LOCAL-HANDOFF.md, TASK-002 and the pinned cross-validation review.
Reuse the installed CMake cache/toolset and existing native core; build only the
replay target. Run targeted regressions, the full repository Python suite and
compileall using the explicit repository venv. Update SOURCES and this report.

The pre-existing RLE draft remains fail-closed with `RLE_NOT_VALIDATED`, including
its pending config/backend tests. Only the redundant unreachable mode condition
in config and trailing whitespace in pending test/build drafts were cleaned.
No native logging implementation, live Stream/cancel, hardware/MCP invocation,
upstream patch, package installation, driver change or commit was performed.

## Implementation and acceptance

- Raw input must be nonempty, at most **32 MiB**, and aligned to **2048-byte**
  native banks. Size is checked before reading; short reads/file growth fail.
  An unaligned tail is rejected without JSON or partial decoded results.
- Convert/read one bank at a time; accept fragment values **0..65536**;
  0 selects one bank, and actual feeds never exceed 2048 bytes. Drain the parser
  queue after every feed; only the first 32 order IDs and fixed counters persist.
  Parser pending frames are bounded by its uint16 payload length; its existing
  consumed-prefix compaction threshold is 32768 bytes. No full-file buffers,
  accumulated sample arrays, or RLE expansion are used.
- Unknown/duplicate/missing arguments, signed/trailing-junk/overflow/over-limit
  fragment sizes, empty/over-limit files and plausible frame bytes in an unknown
  raw tail fail nonzero. Each executable test has a **10-second timeout**.
- Discover the actual `tests/native/build/Release/dl16-raw-rx-replay.exe` output
  (also support a single-config build path). All local executable tests ran:
  no skipped native replay tests.
- Synthetic regressions cover fragment sizes 1/5/17/2048/65536/0, messages across
  banks, 1000 messages with capped summary output, the 32 MiB boundary and an
  unfinished maximum-length frame following a Complete marker.
- JSON reports `evidence_source=OFFLINE_REPLAY`, `input_provenance=UNKNOWN`,
  `data_integrity=UNKNOWN` and `capture_completeness=UNKNOWN`. Complete/ACK fields
  are observations only; Complete alone never certifies sample completeness.

## Exact validations and results

Windows; repository `.venv` Python **3.12.10**; CMake **3.30.1**.
Reused cache: **Visual Studio 17 2022**, **x64**, installed **v142** toolset.
Pinned existing native core source:
`gjjisadog/ATK-Logic-Mcp@5fc47744c18c99f9ad0f554a965eb8cd1160c836`.
No other native target or hardware-probing native suite was run.

```powershell
cmake -S tests\native -B tests\native\build
# Exit 0: configured/generated using existing cache; Windows SDK 10.0.22000.0.
cmake --build tests\native\build --config Release --target dl16-raw-rx-replay
# Exit 0: MSBuild 17.6.3; Release\dl16-raw-rx-replay.exe built.
.venv\Scripts\python.exe -m pytest -q tests\test_raw_rx_replay.py tests\test_config.py tests\test_backend.py
# Final run: 55 passed in 1.65s, exit 0.
.venv\Scripts\python.exe -m pytest -q
# 208 passed in 7.23s, exit 0; no skips.
.venv\Scripts\python.exe -m compileall -q src
# Exit 0, no output.
```

Commands ran with a 120-second tool wait; executable subprocesses independently
use timeout=10. An earlier targeted iteration passed 53 tests before the final
file-limit and incomplete-frame regressions were added. Final rebuild and all
validation commands above succeeded. Evidence is these exact command outcomes,
this tracked report, tests and the ignored local executable in
`tests/native/build/Release`; no physical raw capture was produced.

## Evidence boundaries, risks and next task

Raw-RX logging diagnostics/truncation tests are **CONTRACT_MOCK** subprocess
responses testing Python metadata pass-through. They do **not** establish that
the pinned native executable produces logs, truncates them correctly, writes
hashes, or propagates physical USB logging failures. Synthetic replay is an
offline parser/bank-transform regression, not REAL_HARDWARE or HIL_PASS.

Input provenance remains unknown, parser desynchronization/pending bytes are
observed rather than repaired, and requested channel/sample counts are absent.
Success means bounded replay completed, not that the capture was complete or
well-formed throughout. Same-size file mutation is not authenticated. RLE and
live Stream/cancel remain undelivered/unvalidated. Historical HIL is unchanged.

Next suggestion: allocate a separate task for auditable native raw-RX logging
implementation and offline failure contracts before separately authorized HIL;
do not infer physical logging or live Stream acceptance from this replay.
