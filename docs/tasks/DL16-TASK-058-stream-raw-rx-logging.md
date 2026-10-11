# DL16-TASK-058 — bounded raw-RX logging for experimental Stream

State: **DONE offline implementation / NEEDS_HUMAN_HIL**. Base `b49f5ae`; no commit. Child OFFLINE ONLY / **HIL_NOT_RUN**, parent sole hardware owner. No USB, PWM, reset, firmware, endpoint clearing or driver operations executed.

## Objective, scope, plan

Read AGENTS, LOCAL-HANDOFF, SOURCES, mandatory TASK002/LHX and TASK047, TASK055, TASK057.
In TASK-057, physical 1MHz/1000ms Stream terminated with `SHORT_RX` (1024 bytes) after 65024 bytes (29 reads), before cancellation occurred. However, the raw short read was not retained by the public stream path because raw logging was previously only available on Buffer capture.

This task delivers:
- Optional bounded `dl16-raw-rx/v1` logging inside the actual experimental Stream path prior to transform, including short/error reads.
- Reuses existing `RawRxWriter` with whole-record bounds, writing to generated owner-local `<output_dir>/rx.bin`.
- Combined storage cap: raw RX budget (up to 32MiB) plus packed samples plus 1MiB metadata reservation must fit within 200MiB total.
- Fail-closed disk I/O: write/flush/close errors fail the stream with `ARTIFACT_WRITE_ERROR`.
- Capability-gated: native hello advertises `experimental_stream_raw_rx_v1`; Python session rejects `raw_rx_logging=True` if worker lacks this capability.
- Progress and final metadata accurately expose `raw_rx_log` status (enabled, path, bytes_written, reads, records, truncated, closed, error).
- Short RX fail-closed conversion rule remains unchanged (`SHORT_RX`); raw bytes are preserved for subsequent analysis.

## Acceptance and exact offline results

- `powershell -File scripts\bootstrap-native.ps1 -SkipTests`: exit 0, patch applied cleanly and built.
- `cmake --build tests\native\build --config Release --target dl16-experimental-stream-test`: exit 0.
- `.\tests\native\build\Release\dl16-experimental-stream-test.exe`: exit 0, all native integration tests passed.
- `.venv\Scripts\python.exe -m pytest -q`: **306 passed in 14.52s**, no skips.
- `.venv\Scripts\python.exe -m compileall -q src`: exit 0.
- `git diff --check`: exit 0.

## Parent-only single bounded HIL invocation

Only parent may invoke, after reviewing standard Device lifecycle and confirming existing authorized CH8/14 wiring/shared ground/1.6V, GUI closed and no competing owner.

Run ONE 1MHz/1000ms capture with `raw_rx_logging=True`:
```python
backend.stream_start(
    experimental_opt_in=True,
    safety_confirmation="CONFIRMED_SAFE_WIRING_GUI_CLOSED",
    channels=[8, 14],
    sample_rate_hz=1_000_000,
    duration_ms=1000,
    threshold_voltage=1.6,
    raw_rx_logging=True,
    raw_rx_max_bytes=33_554_432
)
```
Poll until finished; retain all files in artifact directory including `rx.bin` (format `DL16RX01`).
If `SHORT_RX` occurs again, inspect `rx.bin` to analyze the exact short read record and parser state.
Do NOT retry automatically. Do NOT claim cancellation if terminated by `SHORT_RX`.
