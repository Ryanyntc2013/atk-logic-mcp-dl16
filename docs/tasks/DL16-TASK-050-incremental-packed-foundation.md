# DL16-TASK-050 — bounded native incremental packed storage foundation

State: **BLOCKED (live Stream tails) / DONE (offline storage foundation)**.
Base: `3f5ec035b0e2db7c02158de61b8bbc1ae2300a49`. Result commit: **none**, as requested.
Child scope: **OFFLINE ONLY; HIL_NOT_RUN**. No device open, capture, reset, firmware,
driver change, or competing owner operation. Parent owns all hardware work.

## Objective, allowed scope and concrete gate

Implement genuine native incremental packed storage and exercise async start/poll/
cancel on the existing owner dispatcher without a Buffer alias. If safe live Stream
tail semantics cannot be established, stop at an independently useful tested native
foundation. Plan: review mandatory TASK-002/LHX/TASK-049; determine tail evidence;
implement bounded writer and USB-free control harness; fail closed at host/native
boundaries; build full bootstrap with `-SkipTests`, run full venv suite and compile.

The reviewed pinned LHX R4 evidence says Stream **~8 bytes**, Buffer **~12 bytes**,
Buffer+RLE **~1 expanded byte**. These are approximate reported observations, not a
version/model-specific last-packet stripping contract. No independently validated
Stream terminal payload, trigger-offset crop, or owner's Stream physical trace is
available in this checkout. TASK-049 explicitly leaves those semantics unresolved.
Choosing a fixed 8-byte tail or interpreting Order-6 as proof would violate the
existing compatibility/evidence gate. **No live Stream receive loop is delivered.**
No live Stream capability is advertised; async BUFFER is unchanged. This task does
not complete the MCP streaming roadmap or establish HIL_PASS/COMPLETE.

## Delivered native behavior

- `scripts/patches/atk-dl16-incremental-writer.patch` adds the independently authored
  C++17 `IncrementalPackedWriter` to the pinned native include tree. Bootstrap applies
  it after the existing stack and removes only that patch-owned generated header on
  repeated builds. The implementation is persisted in the tracked patch, not solely
  in ignored `external/`.
- Limits: 1–2 unique channels in 0–15, 1–20MHz, 1–30000ms, aggregate packed bytes
  <=200MiB, per-append <=64KiB. Config rejection precedes filesystem operations.
  Exclusive directory creation rejects overwrite. Supplied lower byte caps are
  exercised in native tests. No sample vectors or edges are accumulated by writer.
- Owner writes directly to per-channel files and flushes each chunk: disk I/O is
  backpressure, no sample queue. Existing dispatcher control queue remains capped
  at 8. Storage scales with disk bytes, not RAM; synthetic harness uses one 4KiB
  chunk and bounded metadata/counters. No full-RAM save at finalization.
- All bytes, including hypothetical tails, are retained in LSB-first packed order.
  Metadata records requested samples, Hz, per-channel byte counts and original
  packed index extent starting at 0. These are stored bit positions, **not proven
  valid samples** or a shared physical timebase. `valid_sample_count=null`,
  `tail_status=UNKNOWN`, `partial_uncropped=true`, `edges_omitted=true`.
- Policy `source-conflict-preserve-all-v1` never removes or relabels unknown tails.
  Every artifact is INCOMPLETE, including ordinary synthetic writer termination.
  Explicit CANCELLED/BYTE_CAP/WRITE_ERROR/ABANDONED reasons are preserved. File,
  metadata, flush and close failures surface; destructor best-effort records
  abandonment and never invents completeness. Metadata is updated per chunk but
  is not crash-atomic or power-loss durable; a killed process can leave an invalid
  metadata file or a lagging count. Such artifacts remain untrusted, not COMPLETE.
- Evidence declarations accepted by this foundation are SYNTHETIC_OFFLINE or
  UNKNOWN only; REAL_HARDWARE is deliberately unavailable without a live adapter.
  Storage format `dl16-incremental-packed/v1` is not registered as analysis-ready.

## Async and capability boundary

`tests/native/incremental_writer_test.cpp` compiles the actual patched writer and
production `AsyncDispatcher`. A **synthetic owner**, never Device, writes incrementally
while start/poll/cancel operate. It proves files are visible before completion,
cooperative cancel/final flush, EOF cancellation/join, and INCOMPLETE results. It
uses existing capture_start controls **only as a USB-free test seam**; production
capture_start remains BUFFER and does not route into this writer. No new synthetic
command is enabled in the actual native CLI.

Actual native dispatcher rejects stream_start/stream_poll/stream_cancel with
STREAM_TAIL_UNVERIFIED before owner dispatch/device open. Native hello lacks any
Stream capability. Python NativeSession rejects all three commands before dispatch,
including legacy workers. `logic_stream_start(experimental_opt_in=False)` is an
explicit unavailable-boundary MCP/service/backend tool: without opt-in returns
EXPERIMENTAL_OPT_IN_REQUIRED; opt-in still returns STREAM_TAIL_UNVERIFIED and
stream_available=false without launching a worker or creating artifacts. This tool
is **not** a supported live Stream start and no poll/cancel tools are advertised.
Default one-shot and existing BUFFER behavior are unchanged.

## Versioned vectors and actual execution evidence

`tests/vectors/task050-tail-preservation-v1.json` independently constructs the
source-reported candidate 8/12/1-byte excess cases across split writes. Actual native
harness output preserves every byte/index, remains UNKNOWN/INCOMPLETE and stores no
edges. These are SYNTHETIC_OFFLINE, not validated tail-removal vectors or LHX code.
Additional native tests exercise byte cap rejection without overshoot, overwrite,
abandonment, invalid channel/rate/duration/budget before mkdir, oversized chunk,
wrong channel, closed writer, and concrete metadata write failure. Python tests
exercise old-worker pre-dispatch gates and actual native hello/Stream rejection.

Exact commands/results (2026-10-11):

- `powershell -File scripts\bootstrap-native.ps1 -SkipTests`: exit 0, full patched
  CLI/core built; upstream device-open tests deliberately not run.
- `cmake -S tests\native -B tests\native\build`: exit 0.
- `cmake --build tests\native\build --config Release --target dl16-incremental-writer-test dl16-async-buffer-test --parallel 4`: exit 0.
- `.venv\Scripts\python.exe -m pytest -q tests\test_incremental_writer.py tests\test_async_buffer.py`: **26 passed in 1.56s**.
- After adding native chunk-boundary coverage:
  `cmake --build tests\native\build --config Release --target dl16-incremental-writer-test --parallel 4`: exit 0.
- `.venv\Scripts\python.exe -m pytest -q`: **261 passed in 7.96s**, no skips.
- `.venv\Scripts\python.exe -m compileall -q src`: exit 0.
- `git diff --check`: exit 0; existing workflow Windows line-ending warning only.
- Editor problems: no errors in affected Python source/new test.
- `.venv\Scripts\python.exe -m ruff check tests\test_incremental_writer.py --fix`:
  import ordering corrected; exit 0, no remaining findings. Final test-only
  validation `.venv\Scripts\python.exe -m pytest -q tests\test_incremental_writer.py`:
  **10 passed in 1.19s**. No production changes after full-suite validation.

Ignored evidence logs: `artifacts\task050-build.txt`, `task050-harness.txt`,
`task050-pytest.txt`. Native CI selector now includes writer tests; no remote CI claim.
Native CLI SHA256: `D4811C9AAC607C2AF0EA73083D508C7712CAAFF35C6A332E1D43EBA3621920F3`.
Writer harness SHA256: `263C82AB11EC557A25C0D952B9FFD827FE73412B0C7407DFD79AC04A3B17C1CC`.

## Parent handoff / HIL recipe and next task

**Do not run live Stream from this delivery: there is no approved Stream path.**
First offline parent check: hello/stream_start/close JSONL on fresh native binary
must show no Stream capability, STREAM_TAIL_UNVERIFIED, then successful close;
run only when not interfering with parent's active worker. Current actual tests
already verify this without Device construction.

Next suggested DL16-TASK-051: resolve version/model-specific Stream terminal,
per-channel trailer and offset semantics with explicitly approved bounded raw-RX
capture/replay evidence. Parent must retain device/firmware, confirmed safe signal,
channels/threshold, requested rate/depth, all raw RX read boundaries and hashes,
Order-3/6 fields, first/last waveform samples, cancellation timestamps/stop evidence.
Only after evidence-backed tail vectors pass should the single native owner receive
loop route ChannelData directly to this writer, add real stream_start/poll/cancel
capability and host gating. Proposed first live trial <=2 known channels, <=20MHz,
short duration, <=200MiB, immediate/no-RLE, same owner and GUI closed; no reset,
firmware or drivers. This document is **not authorization** to run a Stream trial.
Acceptance must demonstrate original sample/crop indices, exact valid depth,
partial provenance and cancellation/errors INCOMPLETE before any COMPLETE claim.
