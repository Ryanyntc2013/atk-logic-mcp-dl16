# DL16-TASK-051 鈥?internal bounded Stream raw evidence probe

State: **DONE (parent-ready executable) / NEEDS_HUMAN_HIL (semantics)**.
Base: `3821ade4113487e8639df15c55a91b4957c687af`; result commit: **none**, requested.
Child **OFFLINE ONLY / HIL_NOT_RUN**; no device construction/open, capture, PWM,
reset, firmware, driver, or endpoint operations executed. Parent owns physical HIL.

## Objective, scope and plan

Resolve the concrete missing evidence gate, not tail semantics by assumption:
provide a tracked reproducible opt-in diagnostic harness using pinned native Stream
parameters and existing raw logging; preserve all channel payloads, order3 offsets,
order6 markers and requested sample count. Read AGENTS, LOCAL-HANDOFF, TASK-050,
TASK-002 and pinned LHX review. Implement independently, build smallest target,
run USB-free actual-native frame/bounds and Python rejection tests, record parent
invocation. No public Stream wiring, capture capability, trusted artifact loader,
COMPLETE result, RLE, alternative trigger schema or source-code borrowing.

## Internal diagnostic boundary and bounds

Tracked `tests/native/stream_evidence.cpp`, CMake target `dl16-stream-evidence`, is
**NOT a trusted capture API**. Explicit `--diagnostic-stream-opt-in` bypasses only
public Stream unavailability by using the pinned documented builders/transport in
a standalone narrowly scoped evidence executable. Existing native session/MCP
STREAM_TAIL_UNVERIFIED gates and hello capabilities are unchanged.

- Fixed CH8/CH14 (two channels only), threshold 1.6V, immediate trigger with zero
  trigger position, no RLE. Fixed PWM0 1kHz / PWM1 2kHz, 50% duty using existing
  session PWM helper. Operator confirms these are the already-safe existing wires.
- Supported rates only 1/2/4/5/10/20MHz, requested depth 1..100ms, raw cap
  16..33554432 bytes including header/record framing. Validation before filesystem
  or Device; exclusive new absolute local directory, parent must already exist.
- One Device instance and one synchronous owner thread; no detached workers,
  competing owner, async queue, automatic recovery/reset/endpoint clearing.
- Parameter write and PWM writes <=50ms each, standard DAC settling 30ms.
  Receive deadline **100ms from immediately before trigger write**, trigger write
  <=20ms; reads <=10ms and clipped to remaining deadline. No zero timeout (which
  libusb would interpret as unlimited). Depth does not extend the receive deadline.
- Reads <=16KiB, reserve whole framed record within remaining cap before USB;
  stop at cap without dropping an oversized observed read. Existing RawRxWriter
  logs every capture-phase read/status before bank transformation, even shorts.
- Stop on first Order6, deadline, cap, USB error or write/parser error. Cleanup
  attempts documented capture Stop <=50ms, then both PWM Stops <=50ms each,
  before Device close. `stop_write_ok` proves write returned, not physical idle.
- This is a **cooperative USB deadline**, not hard real-time certification:
  filesystem flush, OS scheduling and standard Device open/query/close can exceed
  wall-clock bounds. No forced process kill is used; receive never waits unbounded
  for Order6. Bounded reads/payload size limit processing work. Do not use a hard
  timeout that kills before cleanup except an actual human-managed emergency.

**Standard Device lifecycle caveat:** pinned `Device::open/close` still performs
its existing query/wake/sleep/flush behavior, identical to the accepted native
owner setup. The harness adds no reset, MCU command or recovery operation; it does
not call extra wake/flush or arbitrary send_command. Parent must assess standard
lifecycle within existing approval before running; if that lifecycle is not
approved, do not invoke. No firmware/upgrade/driver commands added.

## Evidence files / interpretation

New exclusive directory contains `raw-rx.bin` in TASK-047 DL16RX01 framed format,
`channel_0.packed` through `channel_15.packed` and `orders.jsonl`, `summary.json`.
All **actual** parsed channels retained, including unexpected enabled-channel
violations, aggregate parsed payload cap 32MiB in addition to raw cap. Empty files
mean zero observed channel payload, not valid static-low data.

Per-channel sample bytes are LSB-first and untrimmed; no known/assumed ~8-byte tails
removed. Original packet payload hex for Order3/4/6 retained in events. Parsed
Order3 trigger sample offset and 16 channel byte-count fields retained when present;
short/variant Order3 remains raw hex, not invented fields. Order6 count/capacity flag
and ACK observation do not establish gating/completeness. Summary records requested
samples/rate/depth/wiring/PWM, actual per-channel bytes, read count/bytes,
unconverted per-read shorts, parser pending/desync count, stop/PWM-stop outcomes
and explicit termination reason. Raw shorts and final parser residuals remain
recoverable from framed raw log; no cross-read short-bank reinterpretation.

Always `data_integrity=UNKNOWN`, `tail_status=UNKNOWN`, `valid_samples=null`,
uncropped, diagnostic-only; exit 0 only means bounded observation and writes/cleanup
returned without errors. **Not PASS_WAVEFORM, HIL_PASS, COMPLETE or analysis-ready.**
Failure before summary can leave partial raw/channel files; treat as UNKNOWN and
retain stderr. Device identifiers not serialized by harness; parent's environment
record should include redacted model/firmware, pinned build and physical context.

## Acceptance and exact offline results (2026-10-11)

- `cmake -S tests\native -B tests\native\build`: exit 0.
- `cmake --build tests\native\build --config Release --target dl16-stream-evidence --parallel 4`:
  exit 0, links existing pinned patched core and stages existing libusb DLL.
- `tests\native\build\Release\dl16-stream-evidence.exe --self-test`: exit 0,
  SYNTHETIC_OFFLINE mode/bounds/deadline/frame tests passed. No Device construction.
  Exact Stream clear Buffer/RLE flag, 20MHz code6, 400000 requested samples,
  immediate 9-byte trigger CH8/CH14 and deadline clipping asserted. Reject Buffer,
  RLE, non-immediate, third channel, invalid duration/rate and cap boundaries.
- `.venv\Scripts\python.exe -m pytest -q tests\test_stream_evidence.py`:
  **10 passed in 0.14s**; actual executable rejects malformed/missing-opt-in and
  out-of-bounds requests before filesystem/USB. No synthetic data relabeled HIL.
- `.venv\Scripts\python.exe -m pytest -q`: **271 passed in 8.19s**.
- `.venv\Scripts\python.exe -m compileall -q src`: exit 0.
- `git diff --check`: exit 0 (final recheck below); editor problems: none.
- Windows native CI includes new test selector/build target; remote CI not run.
- Executable SHA256:
  `23114694A3A084A2EDD120C9EE02AD23881E8D78D637BA47A9F85DAFE146C604`.

## Parent probe failure and offline correction (2026-10-11)

Parent reports original `stream-01` FAILED before acquisition: `unknown op: start`,
raw_reads=0/raw_bytes=8; Stop/PWM-stop writes returned successfully. Preserve that
original bundle and original executable hash above; **not Stream evidence**.
Root cause: session helper accepts `configure`, not PWM CLI's `start` spelling.
Corrected harness now shares `pwm_frame` between actual acquisition/cleanup and
USB-free self-test. Regression rejects `start` explicitly and verifies exact
configure/stop command0x17 lengths, channel selectors, periods 200000/100000 and
50% counts 100000/50000 for both outputs, using the actual production helper path.
No hardware/no commit during correction.

Correction validation:
`cmake --build tests\\native\\build --config Release --target dl16-stream-evidence --parallel 4`
exit0; `.venv\\Scripts\\python.exe -m pytest -q tests\\test_stream_evidence.py`
**10 passed in 0.14s**; ruff check and git diff --check passed.
Corrected executable SHA256:
`AD298605A5CBEFE656397AE57DB0BAA2FADBA18F6E30EA6AE4B10962BBD9885C`.
Use a **new `stream-02` directory**, never overwrite/relabel `stream-01`.

## Parent stream-02 observation — offline analysis, not acceptance

Parent reports corrected probe physically run; this child only read archived files.
`stream-01` remains the failed pre-acquisition bundle; `stream-02` unchanged.
Raw SHA256 `14344a2eab2c2acdd01966e1bccbd90a7ca7c81b6d732dc378affe6e7fa9c824`.
Versioned sanitized observation: `tests/vectors/task051-stream-observation-v1.json`;
reproducer: `tests/task051_observation.py` (32MiB cap, read-only input). No raw
waveform copying into tracked files, only counts/hashes/short endpoint observations.
Provenance is OFFLINE_ANALYSIS_OF_PARENT_CAPTURE, physical origin parent-declared;
UNKNOWN integrity/alignment/tail and null valid samples retained.

### Observations reproduced from original framed reads

- 74 reads, each 16384 bytes, status0; 1212416 USB payload bytes plus 600 framing
  bytes = 1213016 file bytes. No short banks, malformed records or status errors.
- Native replay: 592 messages, Order1=400, Order2=187, Order3=1, Order4=1,
  Order6=3, desync=405276, pending=0. Desync denotes skipped non-envelope bytes,
  not automatically corruption; its cause is not established by this statistic.
- Independent existing Python reference bank converter/parser reconstructs **all
  16 packed files byte-for-byte** (SHA256s in vector). Every channel has 25 Order1
  packets: 24*2032+1248 = **50016 bytes = 400128 stored bit positions**.
- ACK `ff001203` in read1. Order3 in read2: trigger offset22, 16 fields25001,
  final raw flag byte00. These fields imply 200008 bits if interpreted as simple
  byte counts, far below requested400000; **not reconciled or doubled silently**.
- Three exact Order6 `ff0000` packets are in the same final read74. Harness
  drains every message in an already-returned read before testing Order6; it does
  not issue three acquisitions or continue additional reads after observing it.
- All channels end with exactly sixteen observed `AA` bytes. Extra length is
  16 bytes versus requested 50000, not the ~8-byte reported Stream candidate.
  This is a profile observation, **not a universal tail strip rule**.

### Mode/channel source review and decision

Harness uses Stream/noRLE, fixed CH8/14 and immediate 9-byte trigger. Actual native
self-test checks converted parameter flag00 and rate6; depth400000 is built from
20MHz*20ms. Parameter builder has no channel selector. SimpleTrigger channel-pair
bytes are `00 00 00 00 F0 00 00 F0`, immediate01; native self-test verifies enabled
pairs8/14. No all-channel expansion in harness or parser: channel ID comes directly
from Order1 payload[0], data after two metadata bytes, appended once per message.
Exact reconstruction rules out a harness-only duplication/channel-label artifact.
Both parsers share documented envelope rules; agreement does **not** independently
prove firmware semantics or rule out a structurally valid false frame.

All16 transmission is consistent with the prior HUGEL source-reported warning in
SOURCES.md, but pinned CPP mode/trigger builders alone do not guarantee Stream
transmission is limited to selected channels. No TX wire log is present; source
construction is not proof of device acceptance. Therefore classification is
**OBSERVED_ALL16 / SOURCE-CONSISTENT POSSIBILITY / SEMANTICS_UNKNOWN**, not
expected-by-verified-native-contract and not proven parser artifact. Advertised
2-channel request cannot currently be treated as a physical bandwidth bound.

### PWM observations without crop certification

On the first50000 stored bytes only (a descriptive prefix, not approved crop),
CH8 has20 rising/20 falling transitions, rising positions10022..390022 with
19 intervals20000 stored bits; CH14 has40 rising/40 falling, positions2674..392674
with39 intervals10000. Interior falling/rising separation10000/5000 bits is
consistent with nominal1kHz/2kHz 50% PWM at declared20MHz. This supports recognizable
signal content **only**; no PASS_WAVEFORM, calibrated rate, valid start, common
physical alignment or synchronized skew claim. Full file edge counts84/104 are
contaminated by final AA pattern (63 period2 intervals each); never analyze these
as clean complete waveforms. Offset22 resembles CH8 first falling edge22, but
CH14 differs; no shared-origin/crop conclusion is defensible.

### Exact offline commands, tests and next gate

`tests\\native\\build\\Release\\dl16-raw-rx-replay.exe --raw artifacts\\hil\\DL16-TASK-051\\stream-02\\raw-rx.bin --format dl16-raw-rx-v1 --json`
exit0 with counts above. `.venv\\Scripts\\python.exe tests\\task051_observation.py artifacts\\hil\\DL16-TASK-051\\stream-02`
reconstructs exact packed bytes. `.venv\\Scripts\\python.exe -m pytest -q tests\\test_stream_evidence.py tests\\test_task051_observation.py`:
**12 passed in0.66s**. Profile test portable; archive reconstruction skips when
ignored original is absent, never substitutes synthetic data for physical bytes.

**Next decision gate:** public Stream stays STREAM_TAIL_UNVERIFIED. Before another
physical operation or integration, establish version/model-specific Order3 field
units/layout and terminal AA meaning using pinned vendor documentation/source and
this immutable raw trace; account for all16 transfer budget and duplicate Order6.
A future TX evidence addition must record exact parameter/trigger bytes and firmware
profile without changing channel or trigger protocol. Only a separately approved
controlled capture at a different bounded depth could distinguish fixed16 tail,
alignment padding, half-depth field semantics and acquisition alignment. This
single trace cannot select a crop rule or certify long-running Stream/cancellation.
No more hardware/no commit during this analysis.

## Parent-only corrected invocation (historical; do not automatically repeat)

Close GUI and any prior worker normally; do not auto-kill, rewire or change driver.
Confirm CH8/CH14 remain approved PWM loopbacks, GND and 1.6V threshold are safe.
Check `artifacts\hil\DL16-TASK-051` exists (create only parent folders first).
The destination `stream-02` **must not exist**:

```powershell
New-Item -ItemType Directory -Force artifacts\hil\DL16-TASK-051 | Out-Null
& .\tests\native\build\Release\dl16-stream-evidence.exe `
  --diagnostic-stream-opt-in `
  'E:\code\atk-logic-mcp-dl16\artifacts\hil\DL16-TASK-051\stream-02' `
  20000000 20 33554432
$probeExit = $LASTEXITCODE
Get-Content artifacts\hil\DL16-TASK-051\stream-02\summary.json
Get-Content artifacts\hil\DL16-TASK-051\stream-02\orders.jsonl
Get-FileHash artifacts\hil\DL16-TASK-051\stream-02\* -Algorithm SHA256
```

Parent records exact command, stdout/stderr/exit, executable hash and raw artifact
hashes; first inspect stop/PWM-stop fields and USB errors before any follow-up.
Analyze offsets, per-channel excess versus requested 400000 samples, per-read
alignment and final payloads without trusting Order6 or a successful exit code.
No automatic retry. Next suggested TASK-052: offline replay of that single genuine
Stream archive into versioned tail/offset hypotheses; only then consider a separate
model/firmware-specific completeness contract and public integration.
