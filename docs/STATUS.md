# Release status 鈥?P0 scaffold, updated 2026-10-10

## Source of truth

- Hardware results (LOCAL_HIL): docs/HIL-PHASE-B-STATUS.md is the single authority. This file only indexes task outcomes.
- Lint policy: ruff is required only for modules added after 2026-10-10; pre-existing files are not yet cleaned up, and CI runs pytest and compileall only.
- Evidence capture: scripts/hil-evidence.ps1 -TaskDir artifacts/hil/DL16-TASK-xxx writes environment.json and SHA256SUMS.txt.

## Independently executed checks

- Python offline suite: 69 passing tests on local Python 3.12 (core + DL16-TASK-002/004/005 protocol vectors and export); GitHub Actions Python offline CI successful.
- DL16-TASK-002 Phase A: independent offline protocol reference + byte-level vectors + hash-locked golden artifact; optional native harness confirms the pinned C++ backend matches the Python reference byte-for-byte (protocol frames and RX parsing). Preserved 9B/10B trigger and 25/500 MHz index conflicts. See `docs/research/DL16-TASK-002-phase-a-protocol-vectors.md`.
- DL16-TASK-004 PWM output: offline codec for commands `0x17` (start/stop, 200 MHz counter, channels 0..1) implemented and tested; **LOCAL_HIL on this device** for PWM0->CH0 (100 Hz..20 MHz) and PWM1->CH6 (1 kHz). See `docs/research/DL16-TASK-002-pwm-output.md`.
- DL16-TASK-005 LHX feature adoption: `logic_export` (edge-based VCD / edge-CSV) added offline and exposed via MCP + `dl16ctl export`; roadmap in `docs/research/DL16-TASK-005-lhx-feature-adoption.md`.
- DL16-TASK-006 LHX feature adoption: `logic_filter` (glitch removal -> derived capture) and `logic_search` (multi-channel rising/falling/high/low conditions) added offline, exposed via MCP + `dl16ctl filter|search`. MCP tool surface verified by `tests/test_server.py` (no raw/firmware tool exposed).
- DL16-TASK-007 LHX feature adoption: in-repo offline decoders `decoders.py` 鈥?UART (parity/stop/invert), I2C, SPI (modes 0-3, MSB/LSB, optional MISO/CS); `logic_decode` no longer needs the external checkout.
- DL16-TASK-008 LHX feature adoption: `logic_export` gains full **sample CSV** and **overwrite protection** (LHX file discipline) for export and derived captures.
- DL16-TASK-009: complete agent-facing MCP reference `docs/MCP-TOOLS.md` (tools, native helpers, evidence tiers, output discipline). Offline suite now 82 passing tests.
- DL16-TASK-010 (LOCAL_HIL, operator-approved): **9B vs 10B SimpleTrigger gating resolved** 鈥?the **10-byte** payload gates (edge and level; waits when unmet, completes when met); the pinned **9-byte** payload never gates. Resolves research R2 and B3. See `docs/research/DL16-TASK-010-simple-trigger-gating-9b-vs-10b.md`.
- DL16-TASK-011 (LOCAL_HIL): tracked build patch makes non-immediate SimpleTrigger use the 10-byte gating payload (immediate keeps 9B); offline reference/vectors/golden/native cross-check updated. HIL via MCP CLI: CH0 no-edge `ch0:rising` -> CAPTURE_TIMEOUT (gated), CH8 `ch8:rising` -> success, CH0 immediate -> success. 82 offline tests pass.
- DL16-TASK-012 (LOCAL_HIL): tracked patch exposes `--trigger-position` (pre-trigger %), plumbed through backend/service/CLI/MCP; HIL confirms it reaches the device (order-3 offset tracks total - trigger_depth). Offline suite now 84 passing tests.
- DL16-TASK-013 (LOCAL_HIL, B4): returned-buffer alignment verified 鈥?the trigger edge is at sample `total 脳 position%`, pre-trigger precedes it (100 Hz PWM, position sweep 0/10/50/90 %). Raw packet byte cross-compare still open. See `docs/research/DL16-TASK-013-trigger-alignment.md`.
- DL16-TASK-014 (LOCAL_HIL): multi-channel AND trigger conditions (`ch8:high,ch14:high`) exposed via tracked CLI patch + `logic_capture`; unsatisfiable AND (`ch0:rising` dead channel) correctly gates/timeouts. Edge+level coincidence not certified (fixed PWM phase). See `docs/research/DL16-TASK-014-multi-channel-trigger.md`.
- DL16-TASK-016 (LOCAL_HIL): B-1 shows the multi-channel AND is correct; the earlier timeouts were a fixed-phase artifact of 100 Hz/1 kHz. B-2: 20/20 gated captures timed out at 3.6 s. See HIL-PHASE-B-STATUS.
- DL16-TASK-A1 (offline, reproducibility): all local native changes consolidated into one patch scripts/patches/atk-dl16-local-build.patch (3 files, 23+/11-). ootstrap-native.ps1 now hard-resets the ignored checkout to the pinned commit and applies the patch with git apply --check first. Verified: patch applies cleanly to a fresh clone of the pin; full bootstrap build + 28/28 native tests pass; second run idempotent. .gitattributes keeps the patch bytes unchanged under autocrlf.
- DL16-TASK-015 (LOCAL_HIL): `--trigger-timeout` exposed (tracked patch); a gated capture with `--trigger-timeout 3` returns `CAPTURE_TIMEOUT` in ~3.7 s vs the default 30 s. Offline suite now 89 passing tests.
- Reproduced research R3: `Device::open()` intermittently fails FPGA device-info parse and needs a retry; a 16-channel capture that hit it wedged the device until a physical replug.
- Gate B3 (local, LOCAL_HIL): a simple `ch0:rising` trigger did **not** gate acquisition on this DL16 Plus (MCU v1.9/FPGA v2.22) 鈥?a no-edge capture completed promptly. Reproduces HUGEL, contradicts LHX; simple-trigger gating `UNVERIFIED`. No live encoding changed. See `docs/research/DL16-TASK-002-b3-trigger-gating-2026-10-10.md`.
- Gate B1 (local, LOCAL_HIL): CPP sample-rate indices 1/4/5/6/7/8/9/10/11/12/13 verified via PWM loopback. Index 7 (25 MHz) and index 13 (500 MHz) both work on this unit; LHX's index-7 no-data and 500M->0 were **not** reproduced. See `docs/research/DL16-TASK-002-b1-rate-index-2026-10-10.md`.
- Gate B6 (local, LOCAL_HIL): 20 sequential single-attempt captures gave exactly alternating success/failure 鈥?the `open()` immediately after a completed capture fails FPGA device-info parse, the next succeeds. A bounded retry was added to `backend.py`; the same loop then gave **20/20**. See `docs/research/DL16-TASK-002-b6-reliability-2026-10-10.md`.
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

Consolidated Phase B / HIL scoreboard: `docs/HIL-PHASE-B-STATUS.md`.

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
