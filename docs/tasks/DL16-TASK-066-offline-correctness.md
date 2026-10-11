# DL16-TASK-066 — offline data correctness and failure safety

Status: **implementation on review branch; no hardware exercised**.

Branch: `fix/DL16-TASK-066-offline-correctness`
PR: https://github.com/Ryanyntc2013/atk-logic-mcp-dl16/pull/1

## Changes

1. `logic_filter` exclusively creates a new capture directory. It **never** overwrites an existing capture, even when the compatibility parameter `overwrite=True` is passed. Original file content and original `meta.json` remain unchanged; derived metadata is written last.
2. Filtered captures separate software `processing_status` from source acquisition `capture_complete_received`, `trigger_ack_received`, `data_integrity`; record `source_sha256`, `source_integrity`, original source and transform. The derived artifact must never be promoted from `UNVERIFIED` to `COMPLETE`.
3. UART decoder skips candidate falling edges inside an already consumed frame; back-to-back serial bytes must not spawn false, valid frames.
4. Reject duplicate-channel trigger conditions and explicit host timeouts that cannot encompass trigger wait, acquisition duration and a minimum cleanup margin.
5. Stream offline loader supports explicit per-channel `valid_samples` in `stream_meta.json` and marks byte-count-inferred sample depth as unverified; do not claim calibrated timing.
6. Self-test checks that no existing MCP-owned session is present before touching the device. Every exit path runs bounded cleanup (cancel active Stream, stop both PWM outputs, close owned session). `cleanup_ok=False` blocks positive verdicts. A successful loopback diagnostic is `DIAGNOSTIC_PASS_UNCALIBRATED`, not a calibration certificate.
7. Glitch filtering no longer expands full captures into a sample-per-byte array. It uses bounded/chunked edge extraction and packed-byte range edits, preserving sample counts.

## Offline tests

`tests/test_task066_offline_safety.py` covers:

- original and other existing capture immutability, including overwrite requests
- SHA-256/source-integrity preservation and no synthetic acquisition claims
- consecutive UART framing (0x6B DE F6 49)
- duplicate AND channel and host/device timeout mismatch
- Stream valid-bit-count authority
- already-owned session rejection and PWM-failure cleanup
- failed cancellation or cleanup cannot return healthy
- differential packed glitch filtering against the original bitwise reference over edge cases
- nominal **mocked** self-test results remain explicitly uncalibrated

Run:
```powershell
python -m pytest -q
python -m compileall -q src
```

## Remaining hardware gate (NOT attempted by this PR)

Under operator-confirmed PWM0->CH8 / PWM1->CH14 loopback, GUI closed:

- normal self-test and output-off check using an independent readout
- PWM1 configure failure injection after PWM0 is already active
- active Stream poll timeout / lost response / cancel failure
- physically check PWM stops, USB is released and a fresh status is possible
- preserve logs/artifacts and hashes, report uncertainty rather than promoting an unverifiable result

Never run automatic HIL for this task from CI. Raw/RLE/absolute timing calibration remain out of scope.

## Deployment policy

PR stays draft until offline CI passes, review is complete, and local hardware gate is either performed or explicitly deferred. Main remains unchanged during this offline work.