# ATK-Logic MCP DL16

An **agent-first, headless MCP** workspace for ALIENTEK ATK-DL16 / DL16 Plus.

> Status: **P0 scaffold / HIL_NOT_RUN**. Python offline CI passes; Windows Server 2022 + VS2022 native C++ compilation, CLI smoke test and upstream synthetic/unit tests (**28/28**) pass ([build evidence](https://github.com/Ryanyntc2013/atk-logic-mcp-dl16/actions/runs/38035288929)). Native USB capture relies on a **pinned GPL-3.0 upstream backend** and **HAS NOT BEEN HARDWARE VERIFIED IN THIS REPOSITORY**. Build success is not a physical HIL pass.

## Why this structure?

We intentionally **reuse** mature USB transport, hardware framing, trigger ACK handling, 2048-byte interleaving, buffering and data-integrity checks from [gjjisadog/ATK-Logic-Mcp](https://github.com/gjjisadog/ATK-Logic-Mcp) (pinned to `5fc47744c18c99f9ad0f554a965eb8cd1160c836`) through its CLI. No unverified reimplementation of the USB protocol lives in this project's Python layer.

We add a single MCP entry point with offline `.atkdl` loading and **cross-channel skew / missed-pulse analysis** for 1us-class synchronization experiments. Firmware/capture details are checked against the [official ALIENTEK GUI source](https://github.com/alientek-openedv/atk-logic); decoder design and edge-cases are cross-checked against [sigrokdecode](https://github.com/alientek-openedv/atk_libsigrokdecode) and the community [hugelzhang/atk-logic-mcp](https://github.com/hugelzhang/atk-logic-mcp). The latter two are reference projects, **not** presently embedded as runtime dependencies. See [SOURCES.md](docs/SOURCES.md).

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

The setup script checks out a PINNED upstream source in ignored `external/ATK-Logic-Mcp/`, compiles native CLI and runs its **offline** C++ unit tests. It does not operate a connected device during setup.

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
| `logic_status` | Native adapter | Device identification, firmware, USB state |
| `logic_capture` | Native adapter; **HIL unverified** | Bounded buffer capture and machine-readable artifacts |
| `logic_inspect` | Offline tested | Preview 1..1000 edges with sample/time indices |
| `logic_measure_skew` | Offline tested | Signed pairwise delay, P95/P99, missing/extra pulses |
| `logic_measure_pwm` | Offline tested | Median-period frequency and period jitter |
| `logic_export` | Offline tested | Edge-based VCD / edge-CSV export of one channel |
| `logic_filter` | Offline tested | Glitch removal (drop short pulses) into a derived capture |
| `logic_search` | Offline tested | Sample positions matching multi-channel conditions |
| `logic_decode` | Adapter; requires native checkout | UART/I2C/SPI via pinned upstream Python decoder |

MCP SDK is deliberately pinned to the v1 maintenance API (`mcp>=1.28,<2`) so the tested `mcp.server.fastmcp` entry point does not silently switch major versions.

No `send_raw`, firmware flash, driver installation, undocumented MCU write, or automatically invoked power cycling tool exists in the MCP interface.

## Quality model

- `NOT_EVALUATED`: absent/insufficient waveform or not verified as complete.
- `PASS_WAVEFORM`: signed timing error stayed in bounds **and** no unmatched pulses; numeric waveform conclusion only.
- `FAIL_WAVEFORM`: tolerance exceeded or missing/extra pulses in complete captures.
- `HIL_PASS`: **NOT ISSUED BY THIS SCAFFOLD**; requires operator-confirmed wiring, independent instrumentation and archived real capture evidence.

Native captured bytes and metadata remain in `artifacts/captures/<capture_id>/`, excluded from Git by default. Avoid committing customer signals or serial/device IDs.

## Roadmap

- **P0 (this revision):** repo, agent rules, pinned native bootstrap, MCP gateway, no-hardware tests, basic decoder adapter, vendor `.atkdl` offline loading, skew measurements.
- **P1 (local hardware required):** USB enumeration, verified buffered capture at 1/20/100/200MHz, real trigger gating, source clock cross-check, repeated-run reliability, firmware-specific channel-count behavior.
- **P2:** RLE switch end-to-end, cancellable capture, timeouts in native API, direct `.atkdl` export, configurable pre-trigger ratio and bounded multi-condition triggers, enhanced signal-quality metrics.
- **P3:** optional sigrok protocol host (`uart→modbus`, `spi→spiflash`, etc.), RF-lens custom decoders, calibration and manufacturing HIL reporting.

For what to do next in Codex, see [`AGENTS.md`](AGENTS.md) and [`docs/LOCAL-HANDOFF.md`](docs/LOCAL-HANDOFF.md).

## License and attribution

This project's own integration is licensed **GPL-3.0-or-later**. The pinned native upstream is separately cloned and carries its own GPL notice; vendor projects are **not redistributed here**. This does not imply endorsement by ALIENTEK or any third-party maintainer. Do not paste code from another project's implementation without preserving license and attribution. See `LICENSE` and `docs/SOURCES.md`.
