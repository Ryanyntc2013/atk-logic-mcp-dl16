# Architecture decisions

## ADR-001 Native CLI rather than reimplement USB

**Decision:** Python MCP communicates with `atk-dl16[.exe]` from a pinned revision of `gjjisadog/ATK-Logic-Mcp` over subprocess JSON. It uses the GPL C++17/WinUSB driver core and keeps protocol commands encapsulated there.

**Why:** The upstream sources already implement 0x11/0x12/0x15 framing, CRC, FPGA bank deinterleaving, payload parsing, RLE internals, trigger offsets, channel storage, 30ms settle, and capture integrity checks. A second Python USB implementation would duplicate difficult hardware corner cases.

**Costs:** extra build toolchain, Windows native dependency, default 30s capture watchdog, RLE not currently exposed through CLI, and vendor version changes requiring explicit review.

**Fail-closed:** if native CLI not found or JSON fails validation, MCP returns an explicit error and does not fabricate a capture ID.

## ADR-002 Separate evidence from numeric waveform assessment

Artifact record = `source`, `integrity`, `sample_rate_hz`, `valid_samples`, raw bits and metadata. Numeric `PASS_WAVEFORM` indicates only waveform arithmetic. Physical HIL decisions belong in operator-reviewed reports with wiring and reference calibration.

Do not infer an absolute time-of-day from sample indices. Cross-channel comparisons share the same DL16 sampling clock; comparing signals on different devices requires an independently established timebase alignment.

## ADR-003 Bounded memory and output

Edges are streamed in chunks with LSB-first decode and a maximum edges cap. MCP returns summary and only 20 pair previews or 1000 edge previews; no large waveforms in tool calls. Artifacts stay on disk.

## ADR-004 Optional external protocol decoder

The baseline `logic_decode` imports upstream `analysis.decoders` from ignored checkout after bootstrap, supporting UART/I2C/SPI. Rich sigrok chaining from the additional community repo is listed as future optional adapter and **not described as already implemented**. This avoids misrepresenting standalone sigrok Python decoders as directly executable without their runtime host.

## Decisions deferred

- Windows service / automatic reconnection and multi-device arbitration
- asynchronous capture cancellation and native watchdog extension
- RLE CLI parameter, cross-version USB short packet handling, physical trigger semantics
- `.atkdl` writing compatible with GUI (reading works for known layout)
- RF lens custom protocol semantics and wireless sync calibration certificate
