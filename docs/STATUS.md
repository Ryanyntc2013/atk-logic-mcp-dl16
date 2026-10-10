# Release status — P0 scaffold, updated 2026-10-10

## Independently executed checks

- Python offline suite: 16 passing tests on Linux Python 3.13 and GitHub Actions Python offline CI successful.
- Windows native C++17 / libusb core build: **PASSED** on GitHub-hosted Windows Server 2022, Visual Studio 2022 / MSVC 19.44.
- Pinned upstream native source: `gjjisadog/ATK-Logic-Mcp@5fc47744c18c99f9ad0f554a965eb8cd1160c836`.
- CMake generation, Release compilation and static libusb linkage: **PASSED**.
- Native test executable `atkdl16_tests.exe`: **28/28 tests passed**.
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

## NOT yet verified

- No DL16 is attached to GitHub-hosted runner: **USB enumeration, real capture, trigger behavior and hardware data integrity are not validated**.
- No demonstrated full Windows Python MCP handshake + native USB device end-to-end session; a CLI help smoke test does not prove live capture.
- MCP wire-protocol handshake test was skipped in the initial authoring environment without MCP SDK. CI Python dependencies and tests pass, but this is not a physical MCP/device integration test.
- RLE, stream, calibrated timestamp accuracy, complex triggers and full sigrok PD breadth are not claimed as supported.
- Cross-channel physical timestamp alignment/uncertainty must be verified with a known split signal and reference scope.

## Release criterion

Status remains **P0/SCAFFOLD / HIL_NOT_RUN** until `DL16-TASK-001` documents hardware capture, stable MCP startup and physical skew results. C++ compilation and synthetic tests passing are distinct from HIL certification.
