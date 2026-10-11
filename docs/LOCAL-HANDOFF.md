# Latest continuation — TASK-063, 2026-10-11

DONE. Integrated Stream capture directories (`stream_meta.json` + `ch{channel}.packed.bin`)
into the unified `dl16_mcp.artifacts.load_capture` loader.
Stream channels now seamlessly feed into `logic_inspect`, `logic_measure_pwm`, `logic_export`
(VCD/CSV), `logic_decode` (UART/I2C/SPI), `logic_filter`, and `logic_search` while
faithfully preserving `data_integrity: "INCOMPLETE"`.
Verified against TASK-060 physical hardware capture: CH8 measured 991 cycles at 1000.0Hz
with 0.0ns RMS jitter; CH14 measured 1982 cycles at 2000.0Hz with 0.0ns RMS jitter.
Successfully exported to VCD and verified 992 edges with 1000-sample period.
Validation: **308 full passed**, compileall clean.
Details: [tasks/DL16-TASK-063-stream-export-and-decode.md](tasks/DL16-TASK-063-stream-export-and-decode.md).

# Latest continuation — TASK-062, 2026-10-11

HIL DONE. Probed full Stream sample rate ladder across 2MHz (500ms), 5MHz (200ms),
10MHz (100ms), and 20MHz (100ms) on physical DL16 Plus with PWM loopback.
All rates completed successfully with `reason: DEADLINE`, `cleanup_stop_ok: true`.
Timing profiling confirmed packed disk writing consumes <1.5% of receive time and
chunk flushing consumes <5% of total elapsed time, demonstrating ample I/O headroom
and zero USB backpressure or dropped frames across all supported rates.
Evidence retained in `artifacts/hil/DL16-TASK-062/` (`ladder_results.json`, `native-hash.txt`).
Details: [tasks/DL16-TASK-062-stream-sample-rate-ladder.md](tasks/DL16-TASK-062-stream-sample-rate-ladder.md).

# Latest continuation — TASK-061, 2026-10-11

HIL DONE. Verified long Stream capture (5000ms planned) and live cooperative cancellation.
Physical execution: 1MHz on CH8/CH14 (PWM 1kHz/2kHz) with `raw_rx_logging=True`.
Stream progressed smoothly across 92 reads (stored 1,040,384 bytes across 16 channels),
at which point `logic_stream_cancel` was triggered. Engine terminated within ~40ms on read 93,
flushed all partial writes to disk, cleanly marked `reason: CANCELLED` (`stored_bytes: 1056640`),
successfully sent hardware stop frame (`cleanup_stop_ok: true`), and verified the physical device
remains fully responsive for subsequent queries and clean session closing.
Evidence retained in `artifacts/hil/DL16-TASK-061/` (`result.json`, `records.json`, `native-hash.txt`).
Details: [tasks/DL16-TASK-061-stream-long-cancel-evidence.md](tasks/DL16-TASK-061-stream-long-cancel-evidence.md).

# Latest continuation — TASK-060, 2026-10-11

HIL DONE. Implemented multi-read carry-over buffering in `scripts/experimental_stream.h`.
Partial reads (< 2048 bytes) across USB bulk timeouts accumulate in `raw_carry`
and only whole 2048-byte banks are passed to `convert_to_pc` and `RxParser`.
Validated offline: 21 targeted tests in `test_experimental_stream.py` including
`test_stream_carry_over_fragmented_512` (synthesizing 512-byte USB read fragments);
full pytest **307 passed in 12.33s**.
Physical HIL execution: ran ONE bounded 1MHz/1000ms capture on CH8/CH14 (PWM 1kHz/2kHz)
with `raw_rx_logging=True`. Captured 152 USB bulk reads without aborting.
Stream completed full 1000ms duration cleanly (`reason: DEADLINE`, `stored_bytes: 1983232`,
123,952 bytes per channel across all 16 channels, `short_bytes: 0`).
`rx.bin` analysis revealed 8 separate reads that ended on 512-byte boundaries
(Records 50, 60, 119, 121, 124, 132, 147, 149), all seamlessly accumulated across reads.
Evidence retained in `artifacts/hil/DL16-TASK-060/` (`result.json`, `records.json`, `native-hash.txt`).
Details: [tasks/DL16-TASK-060-stream-carryover-buffering.md](tasks/DL16-TASK-060-stream-carryover-buffering.md).

# Latest continuation — TASK-059, 2026-10-11

HIL DONE. Ran ONE bounded 1MHz/1000ms Stream capture with `raw_rx_logging=True`.
`SHORT_RX` reproduced cleanly after 123,952 bytes (32 reads, 55.3 ms), short_bytes=512.
All 32 records captured into `rx.bin` (523,016 bytes). Records 0..30 are 16,384 bytes
(8 * 2048-byte banks). Record 31 is 14,848 bytes (29 * 512-byte USB packets = 7 * 2048
banks + 512 bytes remainder). The 512-byte tail starts with `0a 01` (Order 1 ChannelData
lane 0). `read_bulk` returned `Error::ok()` (non-fatal timeout on a USB 512B boundary).
Root cause of `SHORT_RX` termination identified: `experimental_stream.h` lacks carry-over
buffering across reads, aborting whenever a USB read ends on a 512B boundary instead of 2048B.
Evidence retained in `artifacts/hil/DL16-TASK-059/`. Stop and session close succeeded.
Details: [tasks/DL16-TASK-059-stream-short-rx-evidence.md](tasks/DL16-TASK-059-stream-short-rx-evidence.md).

# Latest continuation — TASK-058, 2026-10-11

DONE offline / NEEDS_HUMAN_HIL; HIL_NOT_RUN, no commit. Added optional bounded
`dl16-raw-rx/v1` logging into the actual experimental Stream path prior to transform,
preserving exact raw short/error reads (such as the 1024-byte short read in TASK-057)
within a <=200MiB combined storage budget. Reuses existing `RawRxWriter` with
whole-record framing and fail-closed disk errors. Hello advertises
`experimental_stream_raw_rx_v1`, guarded by Python session. Short RX fail-closed
conversion rule remains unchanged (`SHORT_RX`); data integrity remains `INCOMPLETE/UNKNOWN`.
Validation: **306 full passed**, compileall, native harness, diff-check clean.
Parent HIL recommendation: run ONE 1MHz/1000ms capture with `raw_rx_logging=True` to
reproduce and preserve the physical short-RX raw frame evidence.
Exact details: [tasks/DL16-TASK-058-stream-raw-rx-logging.md](tasks/DL16-TASK-058-stream-raw-rx-logging.md).

# Latest continuation ? TASK-057, 2026-10-11

DONE offline / NEEDS_HUMAN_HIL; HIL_NOT_RUN, no hardware/no commit. Stream poll
now exposes bounded atomic actual stored-byte/read progress while running and
measured receive/packed-write/packed-flush elapsed ns; owner-only IO, host unchanged.
Per-chunk flush and existing deadlines/caps unchanged, no throughput or COMPLETE
claim. Actual native integration cancels once after >=64B running progress,
checks bounded partial artifacts/cleanup plus EOF,busy,error,metadata/Stop failures
and counter reset. Final **37 targeted /297 full passed**, compileall,ruff,diff-check
passed; tracked native bootstrap -SkipTests and harness builds passed. Parent only:
ONE1MHz/1000ms capture,<=200 polls/3s,one explicit cancel at first running >0B;
no retries. Exact commands/hash/limitations:
[tasks/DL16-TASK-057-stream-progress.md](tasks/DL16-TASK-057-stream-progress.md).

# Latest continuation ? TASK-055, 2026-10-11

DONE offline implementation / NEEDS_HUMAN_HIL. Actual opt-in experimental native
Stream now uses TASK049 owner and TASK050 incremental writer, not Buffer alias.
All actual16 retained uncropped; INCOMPLETE/UNKNOWN/null valid samples forever;
no analysis readiness, raw logging or edges. Explicit opt-in and safe-wiring/GUI
confirmation, guarded experimental_stream_v1, <=20MHz/30s with all16 budget,
199MiB packed +1MiB metadata reservation. Real start/poll/cancel/EOF integration,
bounded16KiB RX/10ms calls; no full-capture RAM. Tracked patch/bootstrap persisted.
Child OFFLINE ONLY, HIL_NOT_RUN, no commit. Bootstrap -SkipTests and harness built;
29 targeted /289 full passed, compileall/diff-check passed. Parent single bounded
cancel invocation and exact source comparisons/limitations:
[tasks/DL16-TASK-055-experimental-live-stream.md](tasks/DL16-TASK-055-experimental-live-stream.md).
Prior blocked notes below are historical; trusted Stream still unavailable.

# Latest continuation — TASK-054, 2026-10-11

DONE: added import-safe `dl16_mcp.order3_diagnostics` for bounded offline Order3
layout/range reporting. Raw bytes and uint40 values are preserved; signed40 is
explicitly a hypothesis, unsafe unsigned counts are not usable crop/allocation
inputs, and no crop is selected. Buffer convention scope is unchanged; Stream
units/tail/alignment remain UNKNOWN. Versioned TASK051/052/053 multi-depth
regressions and malformed/extreme synthetic cases added. Validation: focused **4 passed**; full `.venv\\Scripts\\python.exe -m pytest -q`
**286 passed in 10.41s**; `.venv\\Scripts\\python.exe -m compileall -q src` and
`git diff --check` exit 0. HIL_NOT_RUN; no USB/native changes and no commit. See
`tasks/DL16-TASK-054-order3-discriminator.md`.

# Latest continuation — TASK-052, 2026-10-11

OFFLINE ONLY / HIL_NOT_RUN; no hardware/no commit. Pinned vendor Order3 byte-count
crop is **Buffer-only**; Stream units and AA meaning remain unresolved. Immutable
TASK051 all16 archive reproduced/hash-checked; versioned executable hypotheses
show fixed16 vs32-byte rounding agree at20ms but diverge at10/30ms. No crop or
public Stream promotion. Internal diagnostic now logs exact2048B TX and linear
parameter/trigger frames plus cached device-open profile (not bus evidence),
with native/reference roundtrip/CRC tests; smallest native target built,
**16 focused /277 full tests passed**, compileall/diff-check passed. Parent-only two-depth proposal
and stop conditions: `tasks/DL16-TASK-052-stream-units-hypotheses.md`. No automatic
HIL approval; stop after first anomaly, never extend deadline/retry to force data.

# TASK-053 depth comparison — offline follow-up

Parent10/30ms20MHz captures preserve all16 channels25008/75008 bytes with8AA
suffix;20ms prior had50016/16AA. Fixed16,universal8 and round32 hypotheses fail.
Order3 fields new profiles are2^40-16 and2^40-8 (signed hypotheses -16/-8), NOT
usable unsigned byte counts;field*2+6 fails even20ms (50008 !=50016).
Exact constructed TX CRC/payload checks verify Stream/noRLE depths and CH8/14-only
immediate trigger; cached model DL16 Plus MCU19/FPGA222. TX is not bus-observed.
Original archives untouched; versioned profiles/reproducer/regressions delivered.
UNKNOWN validity/tails/alignment; public Stream still blocked. Next safe offline
gate: Order3 variant/range discriminator, preserve raw fields, reject impossible
counts before allocation/crop. See TASK053 report. No new HIL/no commit.

# TASK-051 parent evidence follow-up — 2026-10-11

Parent corrected `stream-02` captured all16 channel payloads50016 bytes each,
requested400000 samples,74 aligned reads,Order3 offset22/count fields25001 each,
three Order6 packets in final read. Native replay and independent Python reference
reconstruct original packed files byte-for-byte;16 trailing AA bytes observed on
all channels. All16 is source-consistent possibility, NOT verified channel-selection
semantics. No crop/completeness rule or public Stream gate opened. CH8/14 interior
stored periods20000/10000 are nominal PWM-consistent only; alignment UNKNOWN.
Original stream-01 failure and stream-02 evidence preserved. Versioned observation,
read-only reproducer and archive/profile regressions added; offline focused12 passed.
Next gate: model-specific Order3 units, tails and all16 bandwidth contract before
any separately approved further HIL. See TASK-051 report for exact evidence/counts.

# Latest continuation — TASK-051, 2026-10-11

Parent-ready **internal opt-in diagnostic** `tests/native/build/Release/dl16-stream-evidence.exe`
now sends documented Stream parameters, fixed safe existing CH8/CH14 1.6V with
PWM0 1kHz/PWM1 2kHz 50%, immediate/noRLE. <=100ms depth and receive deadline,
<=20MHz, <=32MiB whole-read framed raw cap, all actual channel bytes/order3/order6
retained uncropped UNKNOWN. Single Device owner, stop/PWM-stop cleanup. No public
Stream integration or COMPLETE promotion. Child OFFLINE ONLY: **271 passed**,
compileall passed, smallest harness built; no hardware/no commit. Parent must review
exact invocation/standard Device lifecycle caveat and stop bounds in
`tasks/DL16-TASK-051-stream-evidence-probe.md` before one diagnostic.

# Latest continuation — TASK-050, 2026-10-11

Offline native incremental packed storage foundation DONE; **live Stream BLOCKED**
by unresolved source-reported approximate tails/crop semantics. Tracked bootstrap
patch, actual USB-free writer + production owner dispatcher tests prove incremental
disk visibility, bounded direct writes, cancel/EOF and fail-closed INCOMPLETE
provenance. No live Stream capability, no BUFFER alias. Explicit unavailable MCP
start boundary rejects even opt-in before launch; legacy workers reject before
dispatch. Full venv suite **261 passed**, compileall passed, native bootstrap
`-SkipTests` and harness built. No hardware/no commit. Parent: do not run live
Stream; next resolve versioned tail/offset evidence before integration. Exact scope,
commands/hashes and HIL gate: tasks/DL16-TASK-050-incremental-packed-foundation.md.

# Latest continuation - TASK-049, 2026-10-11

Genuine opt-in asynchronous cancellable BUFFER foundation added, NOT Stream. Single native Device owner thread, atomic cancellation, capability-gated host/MCP start/poll/cancel, bounded retained bytes and fail-closed partial artifacts. Offline only: no USB, no commit. Full suite 250 passed; compileall passed. Stream incremental persistence/tails/backpressure remain BLOCKED; parent cancellation HIL required. See tasks/DL16-TASK-049-async-buffer-foundation.md for exact parent invocation and limitations.

# Latest continuation ? TASK-048, 2026-10-11

TASK-048 adds explicit `--format raw-banks|dl16-raw-rx-v1` to the actual native
replay target; default raw-banks behavior is retained. Framed replay is capped at
32MiB, preserves read boundaries, reports native status errors/per-record tails
and malformed records, and never promotes completeness. Actual executable tests
cover synthetic boundaries, shorts, errors and truncations. Parent-provided
TASK-047 physical archive was replayed OFFLINE only: 50 records, 819200 aligned
bytes, no errors/tails/malformed records, 400 parsed messages and 414382 desyncs;
orders 1:208, 2:76, 3:1, 4:1, 5:113, 6:1. ACK, offset and Complete marker parsed,
but integrity/completeness remain UNKNOWN and no crop-aligned equivalence is
claimed. No hardware, old MCP or Stream work. See `tasks/DL16-TASK-048-offline-raw-rx-replay.md`.

# Latest continuation — TASK-047, 2026-10-11

TASK-047 delivered tracked native opt-in raw-RX logging before bank conversion,
whole-read framed files capped at 32MiB, fail-closed write/flush/close handling,
explicit truncation/counters and UNKNOWN log completeness. Bootstrap now supports
`-SkipTests` for offline-only builds; the fresh complete patch stack and USB-free
writer harness built successfully. Explicit venv suite: **230 passed**, compileall
passed. No hardware operation; parent owns the live instrument. No commit created.
See `tasks/DL16-TASK-047-native-raw-rx-logging.md` for format, exact commands,
hashes and parent-only bounded HIL recommendation. Existing headerless replay
cannot directly ingest the framed container. Stream/cancel remain separate gates.

# Latest continuation — TASK-043/044, 2026-10-11

User authorized uninstall of the old MCP and continuation. System Python's
`dl16-mcp 1.0.0` editable package was removed (source/shared dependencies retained).
The VS Code user `dl16-mcp` command now points to this checkout's venv Python;
already-loaded MCP tools are not automatically refreshed and were not used.

TASK-043 added 11 offline owner/mixed-worker regressions and strict protocol-1
hello validation. Full venv suite: **183 passed, 1 skipped**; compileall passed.
TASK-044 ran the repository native CLI only, matching retained TASK-034 SHA256.
The first capture had exact CH8/CH14, full sample counts and valid 1kHz/2kHz PWM,
but lacked both required capture-stop cleanup fields. Acceptance FAILED; block
stopped immediately with no replay/second capture. Close returned, not physical
stop certification. See task reports and ignored artifacts/hil/DL16-TASK-044.

TASK-045 reconciled this gate: current ignored serializer source lacked the tracked
stop-observation fields. The full bootstrap rebuilt the patch stack; native suite
34/34 passed (including device-open hardware probe), followed by **2/2** bounded
captures passing PASS_WAVEFORM_UNCALIBRATED with capture-stop fields and waveform
criteria. Close returned. Evidence artifacts/hil/DL16-TASK-045; TASK-044 remains
FAILED and unchanged. No calibrated timing, stream/RLE or unplug claim.
Next: complete the pending offline raw-RX/RLE drafts and independently gate live
Stream/cancel; do not infer broad hardware reliability from two captures.
TASK-046 completed the bounded offline raw-RX replay draft (32MiB input cap,
bank-at-a-time processing, invalid arguments and unaligned tails rejected,
actual native executable regression coverage). Full Python suite **208 passed**,
compileall passed; replay-only CMake target built. Raw-RX logging tests remain
CONTRACT_MOCK, not native logging delivery. RLE requests are fail-closed with
RLE_NOT_VALIDATED. Live RLE and Stream/cancel are still not delivered.
Next task: auditable native raw-RX logging with offline failure contracts, then
separately gated live Stream/cancel; no further hardware test needed for replay.

# Validation environment correction — DL16-TASK-042, 2026-10-11

The system Python 3.14 has an unrelated editable `dl16-mcp` installation pointing
at `D:\code\autoLaD16`. The current VS Code user MCP launch entry uses that system
Python with `-m dl16_mcp.server`; it must not be treated as this repository's MCP.
Do not use the already-loaded `dl16-mcp-*` tools as repository HIL evidence.
No global MCP configuration or installation was changed by TASK-042.

Use `.venv\Scripts\python.exe` explicitly for repository commands. Pytest now puts
`src` and `tests` first on its import path, and an import-provenance regression
asserts that the application and protocol helper originate in this checkout.
This isolation applies to pytest only, not arbitrary system Python commands or
already-running MCP servers. The unfinished raw-RX test's helper imports were
also corrected to avoid an unrelated installed `tests` package.

Validation: `python -m pytest -q` and `.venv\Scripts\python.exe -m pytest -q`
each returned **172 passed, 1 skipped**; `.venv\Scripts\python.exe -m compileall -q src`
passed. The native replay executable remains unavailable/skipped. HIL_NOT_RUN:
this correction performed no capture, PWM, reset or firmware operation.

Next: finish the existing raw-RX/RLE drafts and session reliability gates using
this repository's explicit Python/native executable paths. Preserve historical
HIL evidence separately; neither old-MCP enumeration nor these offline tests
establish a new repository hardware acceptance result.

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


TASK-056 parent normal experimental Stream:20MHz/100ms CH8/14, no PWM change;552704 packed bytes retained, ACK observed, DEADLINE/no Order6, no shorts, Stop fields true and close success. Evidence artifacts/hil/DL16-TASK-056. INCOMPLETE/UNKNOWN unchanged; not sustained throughput or trusted waveform certification. Next bounded gate cancellation after data and profiling incremental flush/backpressure, not deadline extension to force completion.

TASK057 added atomic Stream progress/profiling;297offline tests passed. Parent1MHz/1000ms gate stopped SHORT_RX(1024bytes) after65024packed bytes, before cancel dispatch;Stop/close succeeded. No retry or completeness promotion. Next: preserve short-read raw evidence and validate mode-specific handling; cancellation-after-data still unaccepted.
