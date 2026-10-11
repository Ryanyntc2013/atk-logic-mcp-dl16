# Architecture decisions

## ADR-001 Native CLI rather than reimplement USB

**Decision:** Python MCP communicates with `atk-dl16[.exe]` built from a pinned revision of `gjjisadog/ATK-Logic-Mcp@5fc47744` with tracked repository patches applied via `scripts/bootstrap-native.ps1`. Communication uses subprocess JSON for default one-shot execution and JSONL for opt-in persistent worker sessions (`DL16_BACKEND_MODE=session`).

**Why:** The upstream sources implement 0x11/0x12/0x15 framing, CRC, FPGA bank deinterleaving, payload parsing, RLE internals, trigger offsets, channel storage, 30ms settle, and capture integrity checks. A second Python USB implementation would duplicate difficult hardware corner cases.

**Native deployment prerequisite:** Running native operations requires `atk-dl16.exe` and `libusb-1.0.dll` built and staged via `scripts/bootstrap-native.ps1` (or `scripts/setup-windows.ps1`).

**Cached status semantics:** In persistent session mode, `status` returns cached device identification and capabilities obtained during worker initialization rather than issuing a live query over the FPGA/USB bus on every call.

**Fail-closed:** if native CLI is not found or JSON fails validation, MCP returns an explicit error and does not fabricate a capture ID. In one-shot mode, a narrow B6 retry mitigation handles post-capture FPGA device-info open failures (at most 3 attempts, 0.5s/1.0s backoff).

## ADR-002 Separate evidence from numeric waveform assessment

Artifact record = `source`, `integrity`, `sample_rate_hz`, `valid_samples`, raw bits and metadata. Numeric `PASS_WAVEFORM` (or `PASS_WAVEFORM_UNCALIBRATED`) indicates only waveform arithmetic and tolerance checks. Physical HIL decisions belong in operator-reviewed reports with wiring and reference calibration.

Do not infer an absolute time-of-day from sample indices. Cross-channel comparisons share the same DL16 sampling clock; comparing signals on different devices requires an independently established timebase alignment.

## ADR-003 Bounded memory and output

Edges are streamed in chunks with LSB-first decode and a maximum edges cap. MCP returns summary and only 20 pair previews or 1000 edge previews; no large waveforms in tool calls. Artifacts stay on disk.

## ADR-004 In-repo offline protocol decoders

Deterministic protocol decoders for UART (parity/stop/invert), I2C, and SPI (modes 0-3, bit order) are implemented directly in `src/dl16_mcp/decoders.py`. `logic_decode` runs offline without requiring external checkouts or third-party decoders at runtime. Rich sigrok chaining is listed as a future optional adapter and is **not described as already implemented**.

## ADR-005 Single-owner buffer session lifecycle and failure boundary

**Decision:** Persistent session mode (`DL16_BACKEND_MODE=session` with `DL16_EXPERIMENTAL_SESSION_LIFECYCLE=depth-stop-v1`) executes buffer captures under a single native owner, avoiding per-capture device open/close churn.

**Failure handling:** Any capture failure or trigger timeout immediately invalidates and closes the failed native worker. The system never performs automatic capture replay, retry, or hidden device reset. Subsequent explicit operations spawn a fresh native worker.

Controlled PWM and explicit session close are exposed through MCP/CLI (TASK-034). Safe wiring confirmation and session backend are required; physical output must be measured separately. Real MCP stdio setup/capture/measurement/close passed on the recorded device.

## Decisions deferred

- Continuous streaming capture and RLE CLI parameter exposure
- Multi-device arbitration and automatic reconnection
- Absolute sub-microsecond timestamp calibration and physical skew uncertainty against independent reference instruments
- `.atkdl` writing compatible with GUI (reading works for known layout)
- RF lens custom protocol semantics and wireless sync calibration certificate
