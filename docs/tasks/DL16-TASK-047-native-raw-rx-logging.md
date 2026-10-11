# DL16-TASK-047 — bounded native raw-RX logging

State: **DONE (offline delivery plus bounded logging HIL)**. Parent ran one same-owner CH8/CH14 capture at 20MHz/10ms with 1kHz/2kHz PWM. Exact 200000 samples/channel, numeric waveforms and stop fields passed. Log contained 50 whole records, 819200 payload bytes / 819608 file bytes; closed=true, no error, no truncation. Log SHA256 0600c7e20c8adfa590ffb0bce8e1f1e8fee42ab70810390e4340d43a345d52e4. Evidence artifacts/hil/DL16-TASK-047/physical/request.json, response.json, result.json, rx.bin and journal. Close returned. Log completeness remains UNKNOWN; receive-loop logging excludes prearm/flush traffic, and no full capture replay equivalence or throughput certification is claimed. Base commit:
`d7b8a9d3593fbaba94d16e6dd08f56a95f08453d`. No commit requested or created.

## Objective / allowed scope / plan

Deliver auditable, opt-in native USB receive logging as a prerequisite to a
separate Stream/cancel task. Instrument the existing synchronous capture receive
path before conversion, without changing commands, bank transforms, parser,
termination or crop semantics. Persist as the final tracked bootstrap patch
`scripts/patches/atk-dl16-raw-rx.patch` against the pinned CPP core and preceding
patch stack. Add a USB-free actual native writer seam, thin guarded Python API,
CLI/session capabilities, deterministic failure contracts and CI selectors.
No hardware operation, reset, driver, firmware, raw command or live stream work.
Parent retains single-owner hardware authority.

## Format and safety boundary

Native opt-in: `--raw-rx-path <absolute-new-local-file>` and optional
`--raw-rx-max-bytes <8..33554432>` (default 32MiB). Session capture has equivalent
`raw_rx_path` and `raw_rx_max_bytes` fields. `capabilities` is USB-free and reports
`{"raw_rx_log":"dl16-raw-rx/v1"}`; hello advertises `raw_rx_log_v1`.
Python `backend.capture(..., raw_rx_path=..., raw_rx_max_bytes=...)` validates a
new absolute local file in an existing parent directory, probes capability only
when enabled, and guards the actual session worker hello against mixed generations.
No public MCP flag is exposed; callers may use this bounded backend API or native
CLI, rather than silently passing logging flags to legacy binaries.

File format **dl16-raw-rx/v1**:

- Eight ASCII bytes `DL16RX01`.
- Each synchronous capture `read_bulk` call produces one record: unsigned LE32
  actual length, unsigned LE32 native `ErrorCode` ordinal, then exactly that many
  original bytes, before bank conversion. Includes zero-length/error reads.
- Error ordinals follow pinned `core/include/atkdl16/types.h`: OK=0,
  UsbTransferError=5, DeviceDisconnected=6, CaptureTimeout=14. These are native
  API outcomes, not firmware status bytes. Pin and patch stack must accompany logs.
- Handshake/wake/flush reads are deliberately excluded. Recording starts after
  arming, in the existing receive loop, and ends when that loop exits.
- Limit includes magic and record headers. Only whole records are retained; once
  a record does not fit, no later records are written. Acquisition continues and
  metadata explicitly reports truncation. Never split a bank or USB read to fit.
- For replay, process each record independently: convert only
  `floor(actual_length/2048)*2048` bytes, feed the resulting bytes to one continuing
  parser, and record discarded short/unaligned tails. **Do not concatenate tails
  across reads**. TASK-046's headerless replay tool does not directly accept this
  container; stripping headers and concatenating is valid only when every read is
  bank-aligned. No container replay adapter is claimed in this task.

Exclusive create prevents overwrite. Native rejects relative, Windows network/
device and alternate-stream paths; Python additionally validates parent/file
existence. No directory creation or USB recovery is performed. Header/record
write, flush or close failure fails capture with ARTIFACT_WRITE_ERROR and INCOMPLETE
integrity. Per-record flush is intentional; latency/HIL throughput is unverified.

`raw_rx_log` appears in success and failure JSON, independently of diagnostics:
enabled/path/limit, bytes_written (successfully flushed header/complete records),
payload_bytes, observed_bytes, reads, records, truncated, closed, error, and
completeness=UNKNOWN. On write failure a file may contain an incomplete record;
bytes_written is a committed-prefix counter, **not** an assertion of final file
size. Truncated logs and complete markers do not prove complete USB traffic,
physical generation ownership or HIL. The existing capture serializer's
REAL_HARDWARE field remains a source declaration, never proof for synthetic tests.

## Acceptance and exact local verification

All commands run from `E:\code\atk-logic-mcp-dl16`:

```powershell
powershell -File scripts\bootstrap-native.ps1 -SkipTests
powershell -File scripts\build-vector-harness.ps1
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m compileall -q src
git --no-pager diff --check
```

Fresh bootstrap resets only the ignored pinned checkout, then checks/applies the
entire tracked patch stack. Build output: `atkdl16_core.lib`, `atk-dl16.exe`,
`atkdl16_tests.exe` built successfully; exit 0. `-SkipTests` prevents the upstream
hardware-open probe; native upstream suite deliberately **not run** by this agent.
Harness build exit 0, including `dl16-raw-rx-logging-test.exe`.
Full pytest exact summary: **230 passed in 7.24s**. compileall exit 0, no output.
Diff check exit 0 (only Windows line-ending warnings).

Native writer tests execute actual C++ writer and real files without USB: disabled
behavior, exact raw record bytes/zero-length status records, exclusive collision,
whole-record truncation with continuing observed counters, invalid/missing paths,
32MiB cap, deterministic injected write/flush/close failures, and JSON metadata.
Python includes actual executable capability/session-invalid-request tests,
configuration rejection before launch, legacy binary rejection, disabled/no-probe,
flag forwarding/failure preservation and mixed-generation worker capability guard.
Subprocess mocks are CONTRACT_MOCK only; actual native file tests are
OFFLINE_SYNTHETIC, not physical receive validation. CI selectors include new tests;
no remote CI run claimed.

Evidence retained (ignored): `artifacts\hil\DL16-TASK-047\native-build.txt`,
`harness-build.txt`, `pytest.txt`, `compileall.txt`, `target-tests.txt`.
Binary: `external\ATK-Logic-Mcp\build\Release\atk-dl16.exe` SHA256
`598A72D3C216AB00A7DBCA5FD5B407390D39B8E68A93046281276448CBD4FD6A`.
Patch SHA256 `F5E58FD9681CF4823E82C38A3B532BF9B90EB6A5B9D8FD6A33608FE8F738F768`.

## Parent-only HIL recommendation / next task

After confirming no competing owner/GUI, use the new binary in the parent's
existing single-owner session, adding a **new absolute file** and <=32MiB limit
to its already-approved CH8/CH14, 20MHz, 10ms, immediate, 1.6V capture request.
For one-shot only (never alongside an active session):

```powershell
external\ATK-Logic-Mcp\build\Release\atk-dl16.exe capture --channels 8,14 --sample-rate 20000000 --duration 10ms --threshold 1.6 --trigger immediate --mode buffer --json --out artifacts\hil\DL16-TASK-047\captures --raw-rx-path E:\code\atk-logic-mcp-dl16\artifacts\hil\DL16-TASK-047\physical-rx-v1.bin --raw-rx-max-bytes 33554432
```

Retain JSON/log hashes, verify enabled/closed/no-error/truncation counters and
whole-record framing, compare bank-aligned replay against capture channel counts,
then close the owner. Never promote unknown/truncated logging evidence.
Next: DL16-TASK-048, separately bounded container replay / real Stream-cancel gates;
this task delivers neither asynchronous stream nor physical cancel certification.
