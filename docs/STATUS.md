# Release status — P0 scaffold, 2026-10-10

## Completed in authoring environment

- Standalone Python project, GPL-3.0, MCP v1 FastMCP adapter and CLI.
- Pinned third-party C++ backend bootstrap script, no firmware or USB driver writes.
- Capture JSON sanity gates and file provenance validation.
- Deterministic chunked edge extraction, PWM period/frequency and dual-channel skew (signed ns, unmatched pulses, P95/P99, waveform-level pass/fail).
- Native `.bits` + segmented vendor `.atkdl` offline reading (without falsely calling it a hardware test).
- Documentation: architecture, sources, Windows setup, HIL gates, AGENTS.md, independent task handoff.
- Python offline test suite: 16 passing tests on Linux Python 3.13 + NumPy 2.3.5 (see associated commit).

## Not verified here

- No native C++ Windows build or unit test completed in this authoring environment (no Visual Studio/libusb checkout available).
- MCP wire-protocol handshake cannot be executed here because MCP Python SDK is not installed in offline environment.
- No ATK-DL16 connected; no real-world USB read or trigger gating verified.
- Upstream RLE, stream, calibration and additional sigrok PD are not exposed as claimed complete functionality.
- GitHub target repository is not selected in the connected GitHub App installation; remote push was blocked by 403. Local Git bundle and ZIP are provided for manual import.

## Release criterion

Keep the repo at `P0/SCAFFOLD` until DL16-TASK-001 yields compile/test evidence and first real physical capture. Do NOT label production-ready before live HIL.
