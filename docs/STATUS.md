# Release status — P0 scaffold, updated 2026-10-10

## Independently executed checks

- Python offline suite: 50 passing tests (17 core + 33 DL16-TASK-002 Phase A protocol vectors) on local Python 3.12; GitHub Actions Python offline CI successful.
- DL16-TASK-002 Phase A: independent offline protocol reference + byte-level vectors + hash-locked golden artifact, including preserved 9B/10B trigger and 25/500 MHz index conflicts. See `docs/research/DL16-TASK-002-phase-a-protocol-vectors.md`.
- Windows native C++17 / libusb core build: **PASSED** on GitHub-hosted Windows Server 2022, Visual Studio 2022 / MSVC 19.44.
- Pinned upstream native source: `gjjisadog/ATK-Logic-Mcp@5fc47744c18c99f9ad0f554a965eb8cd1160c836`.
- CMake generation, Release compilation and static libusb linkage: **PASSED**.
- Native test executable `atkdl16_tests.exe`: **28/28 tests passed**.
- Local Windows workstation (VS2022 + v142/v143, Python 3.12): backend rebuilt from the pinned commit via the tracked `bootstrap-native.ps1`; `v142` selected and **28/28** native tests passed. See `DL16-TASK-003`.
- Native CLI `atk-dl16.exe`: produced and launched successfully (help/usage smoke check).
- Windows build evidence: https://github.com/Ryanyntc2013/atk-logic-mcp-dl16/actions/runs/38035288929
- Python CI on same tested tree: https://github.com/Ryanyntc2013/atk-logic-mcp-dl16/actions/runs/38035288927
- GitHub integration has write access; initial scaffold and subsequent CI fixes are on `main`.

## Implemented in scaffold

- Python FastMCP stdio server and CLI, GPL-3.0.
- Pinned GPL-3.0 native C++ USB transport and capture backend built on demand under ignored `external/`.
- Capture JSON integrity gates, native saved-channel files, offline segmented vendor `.atkdl` support.
- Chunked edge extraction, PWM frequency/period, dual-channel skew, missed-pulse analysis and waveform-level verdicts.
- Windows bootstrap scripts; explicit human/HIL gates and coding-agent handoff.

## Independent protocol research added (2026-10-10)

- [LHX DL16 CLI review](research/LHX369963-dl16-cli-cross-validation-2026-10-10.md) compares official sources, pinned native C++, LHX Linux/PyUSB and HUGEL Windows reports. **SOURCE_REVIEWED, not locally reproduced HIL**.
- [DL16-TASK-002](tasks/DL16-TASK-002.md) provides offline contract vectors, model-specific compatibility gates and local-agent handoff.
- Open differences: 25/500 MHz rate indices, 9B/10B trigger frames, MCU/FPGA short packets, order-3 crop, RLE/Stream/Buffer transport tails. No live backend behavior changed by this documentation revision.

## Local build reproducibility (2026-10-10)

- Pinned `bootstrap-native.ps1` now defaults `-Toolset` to the locally installed VS2019 toolset (`v142`) and falls back to the machine default (`v143`) with a warning when it is absent. `-Toolset auto` forces the CMake default.
- The bundled libusb static library is compiled with a NEWER MSVC (front-end 19.39+); local toolsets older than that cannot link it (`LINK : fatal error C1900` Il mismatch, `P1=20240319` constant). The script links the libusb **DLL import library** and stages `libusb-1.0.dll` next to the executables; the pinned commit content is unchanged. Details: `docs/tasks/DL16-TASK-003.md`.

## Local hardware observed (2026-10-10, this workstation, not CI)

- `1a86:ffcc` enumerated; `info` reports **DL16 Plus**, 16 channels, USB 2.0, MCU v1.9, FPGA v2.22.
- Bounded `buffer` capture (CH0, immediate trigger, 20 MHz, 20 ms, 1.6 V) returned `evidence_source=REAL_HARDWARE`, `data_integrity=COMPLETE`, `trigger_ack_received=true`, `capture_complete_received=true`, 400000 samples/channel. Raw artifact kept locally (ignored).
- **HIL_PASS is NOT issued**: no independent-instrument comparison and no real trigger-gating test were performed; these remain `HIL_NOT_RUN`.

## NOT yet verified

- No DL16 is attached to GitHub-hosted runner: **USB enumeration, real capture, trigger behavior and hardware data integrity are not validated**.
- No demonstrated full Windows Python MCP handshake + native USB device end-to-end session; a CLI help smoke test does not prove live capture.
- MCP wire-protocol handshake test was skipped in the initial authoring environment without MCP SDK. CI Python dependencies and tests pass, but this is not a physical MCP/device integration test.
- RLE, stream, calibrated timestamp accuracy, complex triggers and full sigrok PD breadth are not claimed as supported.
- Cross-channel physical timestamp alignment/uncertainty must be verified with a known split signal and reference scope.

## Release criterion

Status remains **P0/SCAFFOLD / HIL_NOT_RUN** until `DL16-TASK-001` documents hardware capture, stable MCP startup and physical skew results. C++ compilation and synthetic tests passing are distinct from HIL certification.
