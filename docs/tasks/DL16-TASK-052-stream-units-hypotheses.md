# DL16-TASK-052 — mode-specific Order3 hypotheses and exact diagnostic TX evidence

State: **DONE (offline scope) / NEEDS_HUMAN_HIL (units/tail contract)**.
Base: `cffc90d53e45980b8377afa757237918fab5705b`; result commit: **none**, requested.
Child OFFLINE ONLY / **HIL_NOT_RUN**. No device construction/open, PWM, USB or
capture was executed. Original TASK051 stream-01/02 files remain unchanged.

## Objective / scope / implementation plan

Read AGENTS, LOCAL-HANDOFF, TASK051, TASK002, its mandatory pinned research and
SOURCES. Direct single continuous source trace, no nested delegation. Compare
pinned vendor receive consumer and native parser against immutable TASK051 archive;
implement independent versioned competing predictions, preserve every byte, add
host-constructed command bytes and cached device profile to internal diagnostic
only, build smallest target and run offline tests. No live protocol, crop, public
Stream capability, integration or completeness changes. No LHX copying/translation.

## Concrete source conclusion: BUFFER units documented, STREAM units unresolved

Pinned VENDOR `alientek-openedv/atk-logic@0dff562d24436def2bec3791684f1911997b9e35`,
[`pv/thread/thread_work.cpp`](https://github.com/alientek-openedv/atk-logic/blob/0dff562d24436def2bec3791684f1911997b9e35/pv/thread/thread_work.cpp):

- Lines 230–278 read Order3 metadata at payload+2, first uint40 LE as trigger
  position. **Only inside `if(isBuffer)`** are the next channel_count uint40 fields
  consumed as byte totals, multiplied by8, compared to sample depth and used to
  calculate per-channel sample start offsets. The source log explicitly calls
  these fields Byte. This is BUFFER source semantics, not proof of Stream units.
- Lines 185–202 divide start sample offsets by8 to remove whole bytes and retain
  bit remainder. Order1 data begins after two metadata bytes. Lines 217–221 count
  payload bytes and multiply by8 for sample-depth progress.
- Lines 321–345 handle Stream Order6 capacity flag and finish reception. There is
  no AA sentinel removal in this receive worker (literal 0xAA/0xaa absent). This
  negative scoped search does **not** prove no FPGA padding or other vendor code
  trims data. Host source does not establish physical AA meaning.
- Order1 consumer uses the received channel ID directly; this path does not
  establish that Stream must transmit only the selected trigger channels.

Pinned CPP `5fc47744c18c99f9ad0f554a965eb8cd1160c836`,
`core/src/rx_parser.cpp` lines154–186 names Order3 fields byte counts for all modes;
`core/src/capture.cpp` lines229–240 multiplies by8 and computes crop offsets.
Vendor's Buffer-only guard is a material scope difference: do not interpret CPP
naming as a verified Stream hardware contract. No runtime fix applied here.
Cached vendor worker SHA256:
`880b2582a92cb1f64599345311c8cb1f8770275b6dc226d4eaa7b049e97bfc49`.
Public sources were fetched to ignored `artifacts/research/TASK052`, not vendored.
LHX approximate8 Stream tail remains REPORTED_HIL only. Prior HUGEL all16 report
is SOURCE-CONSISTENT with this observation, not a selector/bandwidth guarantee.

## Executable competing hypotheses, no crop

`tests/task052_hypotheses.py`, `tests/vectors/task052-hypotheses-v1.json` and
`tests/test_task052_hypotheses.py` preserve exact uint40 raw fields and quantify
alternatives. Archived Order3 offset22, fields25001 each:

- BUFFER-source byte interpretation:25001*8=200008 bit positions.
- Candidate16-bit-word interpretation:25001*16=400016 positions, eight16-bit
  words fewer than observed50016 bytes. Doubling alone does not explain tail.
- Requested400000 bits=50000 bytes. Observed50016 bytes agrees with all three:
  fixed16 surplus; round requested bytes up to32; `2*(depth/16+1)+14`.
  Thus this single capture cannot select units, alignment or padding contract.
- All16 raw channels are reconstructed unchanged; exact trailing run16 AA and
  preceding non-AA are asserted. AA can also be legitimate alternating samples;
  recognizing this suffix never authorizes scanning or stripping arbitrary AA.
- `selected_crop=null`, `valid_samples=null`, UNKNOWN alignment/tails persist.
  Archived SHA256 rechecked through the independent read-only observer:
  `14344a2eab2c2acdd01966e1bccbd90a7ca7c81b6d732dc378affe6e7fa9c824`.

## Additive diagnostic evidence / no protocol behavior change

`tests/native/stream_evidence.cpp` now logs to existing `orders.jsonl`:

- Exact full2048-byte banked transport frame hex plus full2048-byte deinterleaved
  frame hex for parameters and trigger, using the **same vectors actually passed
  to write_bulk**. Authority HOST_CONSTRUCTED_NOT_BUS_OBSERVED: preparation is not
  successful TX, FPGA acceptance or USBPcap proof. Existing send failures remain
  failures; evidence is flushed before PWM/configuration begins.
- Cached `device.info()` from standard open: VID/PID, model enum/name (hex-encoded
  to preserve arbitrary bytes safely), USB speed enum, MCU/FPGA/hardware versions,
  device level/channel count. No extra query or hardware operation. Zero/unknown
  fields explicitly not verified; this profile is not independent identification.
- Native USB-free self-test verifies complete bank transform roundtrip, CRC/footer
  and emits the same serialization with a synthetic quoted model-name fixture.
  Python independently checks exact13-byte parameter payload
  `001006801a0600000000000000` and9-byte trigger `00000000f00000f001` for20MHz/20ms.

Parameter/trigger builders,9B trigger,CH8/14,1.6V,noRLE,PWM,write timeouts,30ms
settling,100ms receive deadline,32MiB caps,stop/cleanup and RX path unchanged.
Event file gains non-RX rows with `kind`, not `order`; consumers must filter.
Historical TASK051 archive has no TX/profile rows: do not backfill or relabel it.
Public STREAM_TAIL_UNVERIFIED gates remain closed.

## Acceptance / exact offline validation (2026-10-11)

- `cmake --build tests\native\build --config Release --target dl16-stream-evidence --parallel 4`: exit0.
- `.venv\Scripts\python.exe -m pytest -q tests\test_stream_evidence.py tests\test_task051_observation.py tests\test_task052_hypotheses.py`: **16 passed in1.12s**, includes actual native self-test, invalid-input no-USB gate, native/reference TX roundtrip/CRC, versioned alternatives and original archive reproduction.
- `.venv\Scripts\python.exe -m pytest -q`: **277 passed in9.01s**.
- `.venv\Scripts\python.exe -m compileall -q src`: exit0.
- `git diff --check`: exit0; edited-file editor diagnostics: no errors.
- Diagnostic executable SHA256:
  `3eb42105f3e37a9d2b8bf8d8c7ef9f96ca31847fcc798560ba3b508fe515b4bc`.
- Hardware NOT RUN; remote CI NOT RUN. Existing full pytest discovery includes
  these Python tests; native-specific tests require built harness as before.

## Narrow next experiment — parent only, separately approved, no automatic run

TASK053 suggestion: two distinct new directories at **20MHz,10ms then30ms**,
same approved CH8/CH14 PWM0/1 loopbacks/GND,1.6V,immediate9B,noRLE; fixed100ms
receive deadline and32MiB raw cap unchanged. First confirm model/profile and review
standard Device lifecycle caveat in TASK051. No resets, retries, rewiring, firmware,
GUI competition,10B variant or additional rate/channel changes. This document is
an experiment proposal, NOT hardware approval.

Discriminating predictions (per received channel; all16 possibility budgeted):
10ms requested25000 bytes: fixed16=25016 vs round32=25024;30ms requested75000:
fixed16=75016 vs round32=75008. Candidate count fields12501/37501 if depth/16+1;
a literal byte-total interpretation matching whole requested depth would instead
be near25000/75000 (possible extras must be reported, not assumed). Hypothesis
`word-count-plus14` predicts same lengths as fixed16 at both depths, so even a
perfect match cannot establish word units or separate those two causes.

Record exact TX/profile/events/raw/packed hashes, all16 count and packet shapes,
Order3 timing/layout, duplicateOrder6, AA suffix run and preceding bytes; no crop.
At30ms all16 sample payload is ~1.20MB, not two-channel150KB: accept deadline
termination as INCOMPLETE/UNKNOWN, never extend bounds to force completion.
If10ms has USB/parser/write error, missing ACK/Order3/Order6, cap/deadline stop,
changed profile, overflow, short/unconverted bytes or failed stop/PWM cleanup:
**stop the block; do not run30ms or retry**. Also stop if bounds or safe wiring are
uncertain. If both bounded observations finish cleanly, stop after those two and
perform offline comparison; no escalation or public Stream release. Offset22 is
not a phase/alignment contract; common physical timebase requires separate signal
and calibrated evidence. Long Stream/cancel/backpressure remain separately gated.
