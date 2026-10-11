# DL16-TASK-048 — bounded offline raw-RX container replay

State: **DONE (offline only)**. This task adds explicit `dl16-raw-rx-v1` replay to the actual native replay executable while preserving the default `raw-banks` format. No live logging behavior, Stream implementation, hardware, old MCP, or USB access was used. No commit created.

## Objective, scope, and acceptance

Add a bounded offline reader for TASK-047's framed raw-RX logs. Input is capped at 32MiB, converted in 2048-byte banks, and parsed without concatenating reads or their tails. Records preserve each read boundary and LE32 length/error ordinal. Short/unaligned payload tails are discarded and reported per record; nonzero read status is counted and does not certify data quality. Incomplete headers/payloads produce explicit malformed-record reporting and nonzero exit after bounded summary. Invalid magic is rejected. All results remain `OFFLINE_REPLAY`, provenance/integrity/completeness `UNKNOWN`.

Synthetic executable acceptance covers retained raw-banks fragment/default behavior, framed multiple boundaries, short and unaligned reads, zero payload, status errors, truncated header/payload, invalid magic, 32MiB file cap and bounded summaries. No Stream/cancel acceptance is included.

## Format behavior

CLI: `dl16-raw-rx-replay --raw <path> [--format raw-banks|dl16-raw-rx-v1] [--frag-size N] [--json]`. Default remains `raw-banks`. Framed mode requires `DL16RX01`; each record is 4-byte unsigned LE payload length, 4-byte unsigned LE native error ordinal, then exactly that record's bytes. Each record converts only its individually aligned bank prefix; tails are skipped, never carried over to a later record. Parser state continues across aligned banks/records. JSON reports format, record count, nonzero status count, discarded tail bytes, malformed record count, parser message/channel order observations, and `UNKNOWN` quality fields. A Complete marker remains a parsed message only.

## Archived physical artifact replay (offline)

Input: parent-provided `artifacts/hil/DL16-TASK-047/physical/rx.bin` (819,608 bytes; TASK-047 records source SHA256 `0600c7e20c8adfa590ffb0bce8e1f1e8fee42ab70810390e4340d43a345d52e4`). Executed only with the local replay executable; no device access. Result: 50 records; 0 status errors; 0 discarded per-record tail bytes; 0 malformed records; 819,200 aligned payload bytes plus 408 container header/magic bytes; 400 parser messages; order counts 1:208, 2:76, 3:1, 4:1, 5:113, 6:1; trigger ACK, trigger offset, and Complete marker observed. Parser reports 414,382 desyncs. Completeness and integrity remain UNKNOWN. These parser/channel-data observations are not a complete capture assertion and are not comparison-equivalence evidence: no appropriate crop alignment/reference comparison was performed.

## Exact validation

From repository root:

```powershell
cmake -S tests\native -B tests\native\build
cmake --build tests\native\build --config Release --target dl16-raw-rx-replay --parallel
.venv\Scripts\python.exe -m pytest -q tests\test_raw_rx_replay.py
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m compileall -q src
```

The targeted native executable tests passed **33/33** after the format extension. Build is limited to the replay target. Full-suite and compileall results are recorded at task completion. Evidence tier: OFFLINE_SYNTHETIC plus OFFLINE_REPLAY of a parent archived physical-source file, not new HIL. Next task may plan Stream separately; this delivery contains no Stream code.
