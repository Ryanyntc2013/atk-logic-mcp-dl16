# ATK-Logic MCP DL16

An **agent-first, headless MCP** workspace for ALIENTEK ATK-DL16 / DL16 Plus.

> Status: **Consolidated release baseline (LOCAL_HIL on DL16 Plus)**. Python offline test suite passes (155 tests); native build and tests pass. Local HIL verified on DL16 Plus (MCU v1.9, FPGA v2.22) for 10-byte trigger gating, pre-trigger position, trigger timeout, multi-channel AND triggers, 20/20 one-shot captures (with B6 mitigation), and 20/20 dual-PWM buffer captures in opt-in persistent session mode (`PASS_WAVEFORM_UNCALIBRATED`). Default backend remains one-shot. Streaming, RLE, and absolute calibration remain unverified.

## Why this structure?

We intentionally **reuse** mature USB transport, hardware framing, trigger ACK handling, 2048-byte interleaving, buffering and data-integrity checks from [gjjisadog/ATK-Logic-Mcp](https://github.com/gjjisadog/ATK-Logic-Mcp) (pinned to `5fc47744c18c99f9ad0f554a965eb8cd1160c836`) through its CLI and session worker, augmented by tracked patches. No unverified reimplementation of the USB protocol lives in this project's Python layer.

We add a single MCP entry point with offline `.atkdl` loading, **in-repo deterministic decoders** (UART, I2C, SPI in `src/dl16_mcp/decoders.py`), and **cross-channel skew / missed-pulse analysis** for synchronization experiments. Firmware/capture details are checked against the [official ALIENTEK GUI source](https://github.com/alientek-openedv/atk-logic); decoder design and edge-cases are cross-checked against [sigrokdecode](https://github.com/alientek-openedv/atk_libsigrokdecode) and [hugelzhang/atk-logic-mcp](https://github.com/hugelzhang/atk-logic-mcp). See [SOURCES.md](docs/SOURCES.md).

## New independent cross-validation (2026-10-10)

The [LHX369963/dl16-cli protocol review](docs/research/LHX369963-dl16-cli-cross-validation-2026-10-10.md) compares pinned vendor, C++ and independent Python implementations, including author-reported DL16 live tests. **Do not treat source agreement or other authors' HIL as this project's hardware acceptance.** Critical unresolved differences: **25/500MHz sample-rate indices, 9/10-byte simple triggers, 512-byte MCU/FPGA replies, order-3 crop and mode-specific tail bytes**. The runtime backend has **not** been replaced.

For local follow-up: first verify the physical device baseline with [DL16-TASK-001](docs/LOCAL-HANDOFF.md), then execute [DL16-TASK-002](docs/tasks/DL16-TASK-002.md) (offline vectors may run before TASK-001 hardware validation; device tests are gated).

## Architecture

```text
Codex / Cursor / Claude / Agent
            |
           MCP (stdio)
            |
   src/dl16_mcp/server.py      <-- only exposed MCP tools
            |
   src/dl16_mcp/service.py     <-- validation & deterministic analysis
       /                 \
 native CLI adapter     offline artifacts + waveform algorithms
       |                 |
 pinned atk-dl16.exe    .bits / vendor .atkdl
       |
 native C++17 / libusb / WinUSB
       |
 physical ATK-DL16 / DL16 Plus
```

## Local deployment (Windows 10/11)

Prerequisites: Windows, Python 3.12 x64, Git, Visual Studio 2022 with **Desktop development with C++**, CMake; original DL16 USB driver (WinUSB) working. Do **not** use Zadig to replace a functioning driver automatically; close the official GUI before opening the device through MCP.

```powershell
# In the cloned repository root
powershell -ExecutionPolicy Bypass -File .\scripts\setup-windows.ps1

# Python/offline tests (no physical DL16 required)
.\.venv\Scripts\python.exe -m pytest -q

# Query native device. Failure when not connected is expected.
.\.venv\Scripts\dl16ctl.exe status
```

The setup script checks out a PINNED upstream source in ignored `external/ATK-Logic-Mcp/`, applies tracked repo patches, compiles the native CLI and stages `libusb-1.0.dll` alongside `atk-dl16.exe`. This native binary deployment is required for hardware capture, 10-byte trigger gating, and session worker execution. The native suite includes `test_device_open_hardware` and may open a connected device; do not treat setup/bootstrap as strictly offline. For the current implementation and hardware evidence baseline, start with [LOCAL-HANDOFF](docs/LOCAL-HANDOFF.md).

If only offline work is possible, use `-SkipNative` during setup. To build later: `powershell -File .\scripts\bootstrap-native.ps1`.

On Linux, Python offline tests work with `python -m pip install -e '.[dev]'`; the native program must be compiled with the system `libusb-1.0` development package, using the pinned upstream CMake project. Hardware support on Linux is unverified.

### Wire up to Codex

```powershell
# Run from the repository root after setup
codex mcp add atk-dl16 -- .\.venv\Scripts\python.exe -m dl16_mcp.server
```

Or manually add to `%USERPROFILE%\.codex\config.toml` (replace with the actual absolute Python path):

```toml
[mcp_servers.atk-dl16]
command = "C:\\path\\to\\atk-logic-mcp-dl16\\.venv\\Scripts\\python.exe"
args = ["-m", "dl16_mcp.server"]
```

For Cursor, add to `.cursor/mcp.json` or the user's MCP settings, with a **full absolute** path:

```json
{
  "mcpServers": {
    "atk-dl16": {
      "command": "C:\\path\\to\\atk-logic-mcp-dl16\\.venv\\Scripts\\python.exe",
      "args": ["-m", "dl16_mcp.server"],
      "env": {"DL16_DATA_DIR": "C:\\path\\to\\dl16-artifacts"}
    }
  }
}
```

`DL16_CLI_PATH` can override the native executable location; `DL16_DATA_DIR` sets the storage root, by default `./artifacts`. Prefer absolute paths in Agent sessions.

### Persistent session mode (DL16-TASK-032)

One-shot remains the default capture mode, with narrow B6 retry mitigation retained for FPGA device-info open failures. Persistent capture is available as an explicit opt-in via `DL16_BACKEND_MODE=session` and `DL16_EXPERIMENTAL_SESSION_LIFECYCLE=depth-stop-v1`.

Dynamic acceptance of the single-owner long-session buffer path passed **20/20** consecutive runs on DL16 Plus (MCU v1.9, FPGA v2.22) with simultaneous 1 kHz / 2 kHz dual-PWM signals on CH8 / CH14 (`PASS_WAVEFORM_UNCALIBRATED`). Calibrated timing, continuous streaming, RLE, and untested hardware revisions remain uncertified. Controlled PWM is exposed via logic_pwm with explicit safe-wiring confirmation and session capability validation; logic_session_close cleans owned outputs. See [TASK-032](docs/tasks/DL16-TASK-032-single-owner-long-session.md).

**Failure and recovery semantics:** Any capture timeout or protocol error invalidates and closes the failed native worker without auto-replay or hidden USB reset. A subsequent explicit operation creates a fresh native worker. Seamless in-session timeout recovery is not supported; close and owned-PWM cleanup errors are surfaced.

**Cached status semantics:** In persistent session mode, `status` returns cached device descriptors and state captured during worker initialization rather than querying the FPGA over USB on every call.

The optional `DL16_SESSION_JOURNAL_DIR` setting enables local, durable request/response evidence for session mode. Use an absolute path in an ignored task evidence directory. Journal files record host declarations, native responses, and signal metadata. Logging is host-side evidence, not raw USB traffic or calibration certification.

See [TASK-020 session journal](docs/tasks/DL16-TASK-020-session-evidence-journal.md) and [TASK-032 single-owner acceptance](docs/tasks/DL16-TASK-032-single-owner-long-session.md). Setting logging options does not authorize hardware access; device connection, safe wiring and voltage must be confirmed before live commands.

### Local capture example (ONLY with known safe wiring)

```powershell
# CH0/CH1, buffer mode, 10MHz x 100ms, input threshold 1.5V
.\.venv\Scripts\dl16ctl.exe capture --channels 0,1 --sample-rate-hz 10000000 --duration-ms 100 --threshold 1.5 --trigger immediate

# If capture returns an ID, check two-channel skew with 1us tolerance
.\.venv\Scripts\dl16ctl.exe skew CAPTURE_ID --ref 0 --target 1 --limit-ns 1000
```

**Important:** a successful CLI result requires `data_integrity=COMPLETE`, `capture_complete_received=true`, `trigger_ack_received=true`; this still does not prove physical trigger gating or absolute timing accuracy. Skew results report signed delay (target - reference), missed pulses, P95/P99 and waveform verdict. For independent 1us accuracy validation, refer to [HIL-TEST-PLAN.md](docs/HIL-TEST-PLAN.md).

## MCP tools currently exposed

| Tool | Status | Description |
|---|---|---|
| `logic_status` | Native adapter (cached in session mode) | Device identification, firmware, USB state |
| `logic_capture` | Native adapter; gating/position HIL-verified | Bounded buffer capture; edge/level and multi-channel AND triggers gate (10-byte payload); `trigger_position_percent` sets pre-trigger |
| `logic_inspect` | Offline tested | Preview 1..1000 edges with sample/time indices |
| `logic_measure_skew` | Offline tested | Signed pairwise delay, P95/P99, missing/extra pulses |
| `logic_measure_pwm` | Offline tested | Median-period frequency and period jitter |
| `logic_export` | Offline tested | VCD / edge-CSV / sample-CSV export of one channel |
| `logic_filter` | Offline tested | Glitch removal (drop short pulses) into a derived capture |
| `logic_search` | Offline tested | Sample positions matching multi-channel conditions |
| `logic_decode` | Offline tested | UART (parity/stop/invert), I2C, SPI (modes 0-3, bit order), in-repo |

MCP SDK is deliberately pinned to the v1 maintenance API (`mcp>=1.28,<2`) so the tested `mcp.server.fastmcp` entry point does not silently switch major versions.

Full parameter reference, native helper tools and evidence tiers: [docs/MCP-TOOLS.md](docs/MCP-TOOLS.md).

Controlled PWM and explicit session close are exposed through MCP/CLI (TASK-034). Safe wiring confirmation and session backend are required; physical output must be measured separately. Real MCP stdio setup/capture/measurement/close passed on the recorded device.

## Quality model

- `NOT_EVALUATED`: absent/insufficient waveform or not verified as complete.
- `PASS_WAVEFORM`: signed timing error stayed in bounds **and** no unmatched pulses; numeric waveform conclusion only (`PASS_WAVEFORM_UNCALIBRATED`).
- `FAIL_WAVEFORM`: tolerance exceeded or missing/extra pulses in complete captures.
- `HIL_PASS`: **NOT ISSUED** without independent instrument calibration, operator-confirmed wiring, and archived physical capture evidence.

Native captured bytes and metadata remain in `artifacts/captures/<capture_id>/`, excluded from Git by default. Avoid committing customer signals or serial/device IDs.

## Roadmap

User approved full roadmap including all features plus exposing controlled PWM as MCP/CLI:
- **Phase 1 (Consolidated baseline — DL16-TASK-033):** repo, deterministic offline analysis, in-repo UART/I2C/SPI decoders, 10-byte trigger gating, position alignment, timeout, AND triggers, 20/20 one-shot captures (B6 retry), opt-in persistent buffer session with 20/20 dual PWM (`PASS_WAVEFORM_UNCALIBRATED`).
Controlled PWM and explicit session close are exposed through MCP/CLI (TASK-034). Safe wiring confirmation and session backend are required; physical output must be measured separately. Real MCP stdio setup/capture/measurement/close passed on the recorded device.
- **Phase 3 (Future):** RLE switch end-to-end, streaming capture, direct `.atkdl` export, multi-device arbitration, and external sigrok protocol host adapter.
- **Phase 4 (Future):** calibrated timestamp accuracy against reference instruments, RF-lens decoders, and manufacturing HIL certification.

For what to do next in Codex, see [`AGENTS.md`](AGENTS.md) and [`docs/LOCAL-HANDOFF.md`](docs/LOCAL-HANDOFF.md).

## License and attribution

This project's own integration is licensed **GPL-3.0-or-later**. The pinned native upstream is separately cloned and carries its own GPL notice; vendor projects are **not redistributed here**. This does not imply endorsement by ALIENTEK or any third-party maintainer. Do not paste code from another project's implementation without preserving license and attribution. See `LICENSE` and `docs/SOURCES.md`.


### Experimental asynchronous Stream (TASK055)

Current rebuilt session workers expose opt-in `logic_stream_start/poll/cancel`
with `experimental_stream_v1` capability guard. Start requires explicit
`experimental_opt_in=True`, `safety_confirmation="CONFIRMED_SAFE_WIRING_GUI_CLOSED"`
and confirmed channels/threshold. This is genuine Stream, not trusted capture:
all actual16 channel bytes retained incrementally, uncropped INCOMPLETE/UNKNOWN,
null valid samples, no edges/analysis. <=20MHz/30s and conservative all16 aggregate
200MiB budget;20MHz/30s is rejected. No hardware validation by child.
See [TASK055](docs/tasks/DL16-TASK-055-experimental-live-stream.md) for exact limits,
source comparison, tests and parent-only single bounded cancellation invocation.
