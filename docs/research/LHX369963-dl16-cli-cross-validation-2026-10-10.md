# Independent DL16 protocol cross-validation: LHX369963/dl16-cli

**Date:** 2026-10-10  
**Status:** SOURCE_REVIEWED / CROSS-CHECKED; **NOT** reproduced on this project's physical DL16  
**Research task:** DL16-TASK-002 (implementation and local HIL follow-up)  
**Scope:** DL16 protocol compatibility and evidence. **No backend replacement or firmware operation approved.**

## 1. Source snapshots and evidence discipline

| Short name | Repository | Pinned source revision / role |
|---|---|---|
| VENDOR | [alientek-openedv/atk-logic](https://github.com/alientek-openedv/atk-logic/tree/0dff562d24436def2bec3791684f1911997b9e35) | `0dff562d24436def2bec3791684f1911997b9e35`: vendor Qt USB/control/receive implementation |
| CPP | [gjjisadog/ATK-Logic-Mcp](https://github.com/gjjisadog/ATK-Logic-Mcp/tree/5fc47744c18c99f9ad0f554a965eb8cd1160c836) | `5fc47744c18c99f9ad0f554a965eb8cd1160c836`: **current actual runtime** C++ backend |
| LHX | [LHX369963/dl16-cli](https://github.com/LHX369963/dl16-cli/tree/8d7c209c1e3b13923620bb34cec915291a749612) | `8d7c209c1e3b13923620bb34cec915291a749612` (2026-08-19): independent Linux Python/PyUSB CLI |
| HUGEL | [hugelzhang/atk-logic-mcp](https://github.com/hugelzhang/atk-logic-mcp/tree/77320addfb34d3973d09a7af663de76023034587) | `77320addfb34d3973d09a7af663de76023034587`: independent Windows tests and USBPcap observations |
| MCP | [Ryanyntc2013/atk-logic-mcp-dl16](https://github.com/Ryanyntc2013/atk-logic-mcp-dl16) | Python FastMCP gateway + CPP adapter + offline analysis; hardware validation pending |

Evidence labels used below:
- **SOURCE_AGREEMENT**: comparison of checked-in source / documentation; not an independent physical measurement.
- **REPORTED_HIL**: another author's published hardware-test result, not repeated by this project.
- **SOURCE_CONFLICT**: checked-in implementations disagree, requiring test or version discrimination.
- **HIL_REQUIRED**: cannot claim correct behavior for the user's specific DL16 until local device/firmware measured.

Important provenance boundary: LHX's disassembly `reverse/` files and many raw wire / capture artifacts referenced by its acceptance reports are excluded from that public source tree. Its HIL results are **author-reported**; they are useful but not equivalent to locally captured reproducible evidence. The public LHX tree does not contain an explicit `LICENSE` file at this snapshot; **do not copy or vendor its source into this GPL repository without permission / license resolution**. This document only records comparisons, facts, and test directions.

## 2. Areas of agreement

| Component | Checked implementation and evidence | Assessment |
|---|---|---|
| Primary USB identity / endpoints | VID:PID `1A86:FFCC`; bulk OUT `0x02` / IN `0x81` in VENDOR, CPP and LHX | SOURCE_AGREEMENT (primary DL16 only; LHX also lists two other VID:PIDs requiring model checking) |
| Command IDs | 0x10 device info; 0x11 parameters; 0x12 simple trigger; 0x15 stop; 0x17 PWM | SOURCE_AGREEMENT |
| Command frame | Eight zero bytes + `0x0A` + (command, length=payload+1, payload) + `0x0B` + CRC32 little endian, then zero padding | SOURCE_AGREEMENT |
| CRC flavor | CRC-32 reflected polynomial `0xEDB88320`, internal seed 0, final XOR `0xFFFFFFFF`; `crc32("123456789")=0xD202D277`, **not** default `zlib.crc32` | SOURCE_AGREEMENT |
| 2048-byte FFCC bank conversion | Four lanes of 16-bit words, 512 bytes per lane, inverse for TX and RX | SOURCE_AGREEMENT |
| RX envelope | `0x0A`, order 1..6, payload length LE16, payload, `0x00 0x0B`; packet boundary independent of USB chunk boundary | SOURCE_AGREEMENT |
| Channel sample bytes | order 1, channel ID in first metadata byte, sample bytes after 2 metadata bytes; 8 chronological samples per byte LSB-first | SOURCE_AGREEMENT |
| RLE block | `(repeat_count, packed_byte)` pairs; expansion must be bounded | SOURCE_AGREEMENT; full capture path still HIL_REQUIRED |
| Parameters | 13B payload: mode flags (Buffer 0x80, RLE 0x40), signed 0.1V threshold, sample-rate index, uint40 LE sample depth, uint40 LE trigger position | SOURCE_AGREEMENT |
| Return codes | order 3 trigger offset, order 4 control ACK, order 5 progress, order 6 completion | SOURCE_AGREEMENT; acceptance semantics require HIL |

Primary code:
- [VENDOR `pv/usb/usb_control.cpp`](https://github.com/alientek-openedv/atk-logic/blob/0dff562d24436def2bec3791684f1911997b9e35/pv/usb/usb_control.cpp)
- [VENDOR `pv/controller/session_controller.cpp`](https://github.com/alientek-openedv/atk-logic/blob/0dff562d24436def2bec3791684f1911997b9e35/pv/controller/session_controller.cpp)
- [CPP `core/src/protocol.cpp`](https://github.com/gjjisadog/ATK-Logic-Mcp/blob/5fc47744c18c99f9ad0f554a965eb8cd1160c836/core/src/protocol.cpp)
- [CPP `core/src/rx_parser.cpp`](https://github.com/gjjisadog/ATK-Logic-Mcp/blob/5fc47744c18c99f9ad0f554a965eb8cd1160c836/core/src/rx_parser.cpp)
- [LHX `dl16_cli/protocol.py`](https://github.com/LHX369963/dl16-cli/blob/8d7c209c1e3b13923620bb34cec915291a749612/dl16_cli/protocol.py)
- [LHX `dl16_cli/capture.py`](https://github.com/LHX369963/dl16-cli/blob/8d7c209c1e3b13923620bb34cec915291a749612/dl16_cli/capture.py)

## 3. Critical differences; **do not silently reconcile**

### R1 / CRITICAL — DL16 sampling indices and model limits

`CPP sample_rate_to_code()` maps 25 MHz -> 7 and 500 MHz -> 13, and `CPP capability.cpp` grants 500 MHz only to DL16 Plus. LHX tested 20 MHz -> 6, reports index 7 yielded no type-1 samples in **three** fresh DL16 captures, and maps 500 MHz -> **index 0 on DL16**. Its verified rate table is 1, 2, 4, 5, 10, 20, 40, 50, 100, 200, 250, 500 MHz. This is a **SOURCE_CONFLICT**; different hardware models, firmware and software versions may explain it, but that is not established.

**Local decision gate:** identify precise model / firmware and check physical PWM period in samples at supported 20/40/250 MHz; test 25/500 MHz only if allowed by confirmed hardware specs. For failing rate 7, capture USB and log no-data vs timeout; do not change the native mapping without a device-specific capability table and reproducible test. Test no-support must fail closed; no silent fallback to 20 MHz.

Sources: [CPP protocol](https://github.com/gjjisadog/ATK-Logic-Mcp/blob/5fc47744c18c99f9ad0f554a965eb8cd1160c836/core/src/protocol.cpp), [CPP capability](https://github.com/gjjisadog/ATK-Logic-Mcp/blob/5fc47744c18c99f9ad0f554a965eb8cd1160c836/core/src/capability.cpp), [LHX sampling](https://github.com/LHX369963/dl16-cli/blob/8d7c209c1e3b13923620bb34cec915291a749612/docs/protocol/sampling.md).

### R2 / HIGH — simple-trigger payload length and gate semantics

- VENDOR checked-in `SessionController::start` builds **8 channel-pair bytes + 1 immediate flag** = **9 bytes**.
- Pinned CPP `build_simple_trigger_frame` likewise uses **9 bytes**.
- LHX `build_simple_trigger_payload` uses **8 channel-pair bytes + 2 collect-type bytes** = **10 bytes**.
- HUGEL reports a Windows ATK-Logic **1.1.2.1** USBPcap command with eight `0xFF` bytes followed by `00 00`: **10 bytes**, consistent with LHX's Linux binary analysis. Device firmware compatibility with both formats **not established**.
- The nibble itself is consistent: high nibble for even channel, low for odd; enable bit `0x8`; enabled rising `0x9`, falling `0xA`, etc.
- **Independent disagreement:** LHX reports edge triggers localized near a configured 50% position, while HUGEL reports constant-level capture completed despite waiting for an edge on its firmware. ACK is not evidence of actual gated acquisition.

**Local decision gate:** compare 9B/10B payload only via offline construction at first; on real DL16, test idle-no-edge against edge-trigger request and delayed known edge. Measure arming-to-start, actual trigger index, ACK and order-3, and behavior across repeated captures. Do not auto-send undocumented/experimental trigger variants without operator-approved controlled test. Set trigger status `UNVERIFIED` unless genuine gating observed.

Sources: [VENDOR trigger builder](https://github.com/alientek-openedv/atk-logic/blob/0dff562d24436def2bec3791684f1911997b9e35/pv/controller/session_controller.cpp), [CPP trigger builder](https://github.com/gjjisadog/ATK-Logic-Mcp/blob/5fc47744c18c99f9ad0f554a965eb8cd1160c836/core/src/protocol.cpp), [LHX trigger](https://github.com/LHX369963/dl16-cli/blob/8d7c209c1e3b13923620bb34cec915291a749612/dl16_cli/trigger.py), [HUGEL report](https://github.com/hugelzhang/atk-logic-mcp/blob/77320addfb34d3973d09a7af663de76023034587/atk-logic/TEST-REPORT.md).

### R3 / HIGH — connection handshake and USB transfer boundaries

VENDOR FFCC sample transport normally de-interleaves **only whole 2048B blocks**, while short MCU/FPGA responses can be 512B/raw. LHX handles short responses independently, initializes via MCU `0x81` and FPGA `0x87` handshake, and reports that explicitly setting USB configuration can stall endpoints until physical replug. HUGEL also documents 16KB aligned URBs mixed with 512B short responses. CPP's FPGA info query requires an aligned 2048B return in its current code; this may reject otherwise valid firmware-dependent short responses.

**Local decision gate:** confirm raw lengths/return types, how transfers are reassembled, and path-specific de-interleaving before changing behavior. Never feed 512B handshakes into 2048B reordering. Automatic `clear_halt`, USB reset and firmware state changes require the existing AGENTS.md approval boundaries: **do not add automatic USB reset simply because LHX uses it**.

Sources: [CPP device init](https://github.com/gjjisadog/ATK-Logic-Mcp/blob/5fc47744c18c99f9ad0f554a965eb8cd1160c836/core/src/device.cpp), [LHX USB](https://github.com/LHX369963/dl16-cli/blob/8d7c209c1e3b13923620bb34cec915291a749612/dl16_cli/usb.py), [LHX transport](https://github.com/LHX369963/dl16-cli/blob/8d7c209c1e3b13923620bb34cec915291a749612/docs/protocol/transport.md).

### R4 / HIGH — order-3 start cropping, sample tails and shared timebase

LHX reports mode-dependent extra packed bytes: ordinary Buffer often **~12B**, Buffer+RLE **~1 expanded byte**, Stream **~8B**. It truncates by expected sample depth, retains raw `wire.bin`, handles multi-channel packets and streaming incrementally. HUGEL independently reports corrupted frequency measurements when post-depth residue is counted as samples. CPP *already* parses order-3 offsets, applies `channel_start_offsets` and finalizes sample counts; **do not incorrectly claim offset handling is absent**.

**Local decision gate:** use controlled edge near trigger, 50% pre-trigger and two same-source channels. Compare (1) raw RX, (2) per-channel packed bytes before/after crop, (3) per-channel valid samples, (4) order-3 offset and trim, (5) identical physical edge positions after crop. Verify any result marked COMPLETE is actually time-aligned; incomplete metadata must not be silently treated as a valid 1 us sync measurement. Do not compare absolute sample indices from separately started captures as a shared timebase.

Sources: [CPP capture](https://github.com/gjjisadog/ATK-Logic-Mcp/blob/5fc47744c18c99f9ad0f554a965eb8cd1160c836/core/src/capture.cpp), [VENDOR receive](https://github.com/alientek-openedv/atk-logic/blob/0dff562d24436def2bec3791684f1911997b9e35/pv/thread/thread_work.cpp), [LHX acquisition](https://github.com/LHX369963/dl16-cli/blob/8d7c209c1e3b13923620bb34cec915291a749612/dl16_cli/acquisition.py), [HUGEL report](https://github.com/hugelzhang/atk-logic-mcp/blob/77320addfb34d3973d09a7af663de76023034587/atk-logic/TEST-REPORT.md).

### R5 / MEDIUM — additional USB identities, PWM and long-lived sessions

LHX accepts `1A86:FFCC`, `1A86:6A6B`, `04B4:6A6A`. Those are not proof all models behave the same. LHX's report documents DL16 dual PWM (including a **200 MHz** PWM counter clock), multi-channel capture, RLE expansion, long Stream writes, a persistent JSONL session, VCD/CSV export and a sigrok-cli decoder path. CPP does not expose all those features through the pinned CLI / this MCP.

**Do not widen device whitelist automatically.** Prefer a separate, operator-approved P2 feature task for PWM loopback and persistent session after gate-0 and gate-1 capture work. Session lifecycle must preserve exclusive USB ownership and clean stop. Linux-specific `udev` instructions do not apply to Windows WinUSB driver installation.

Sources: [LHX PWM](https://github.com/LHX369963/dl16-cli/blob/8d7c209c1e3b13923620bb34cec915291a749612/docs/protocol/pwm.md), [LHX session](https://github.com/LHX369963/dl16-cli/blob/8d7c209c1e3b13923620bb34cec915291a749612/dl16_cli/session.py), [LHX acceptance 2026-07-18](https://github.com/LHX369963/dl16-cli/blob/8d7c209c1e3b13923620bb34cec915291a749612/docs/acceptance-2026-07-18.md).

## 4. LHX author's HIL evidence (not independently reproduced)

The publicly checked-in [2026-07-15](https://github.com/LHX369963/dl16-cli/blob/8d7c209c1e3b13923620bb34cec915291a749612/docs/acceptance-2026-07-15.md) and [2026-07-18](https://github.com/LHX369963/dl16-cli/blob/8d7c209c1e3b13923620bb34cec915291a749612/docs/acceptance-2026-07-18.md) reports describe PWM0/1 loopback to CH7/CH6/15, 250 MHz 4/8/16-channel Buffer captures, trigger tests around 50%, extended RLE (e.g. 131.25 MB aggregate decompressed samples), interrupted Stream acquisition retaining aligned channel samples, sigrok external decode, and **193 pytest** cases. Those are the author's reported outcomes; **we did not execute those tests on the owner's device**.

Avoid calling a successful software test, C++ compilation, reported capture or ACK a verified physical capture by this repository.

## 5. Cross-implementation test vectors to add in DL16-TASK-002

| Vector | Expected / question | Acceptance |
|---|---|---|
| CRC vector | `123456789 -> D202D277`; empty -> `FFFFFFFF` | Same command CRC bytes across Python and CPP |
| TX framing | 8 zero prefix, `0A`, command/length, `0B`, LE CRC, zero padding | Compare same command/payload after undoing 2048B interleave |
| Bank transform | Deterministic 2048B sequence and inverse; multi-URB; unaligned 512B handshake | Round-trip full blocks; preserve raw short response |
| Trigger nibble | CH0 rising `0x90`, CH1 rising `0x09`, CH7 rising in byte 3 low nibble | Same nibble across all three reference implementations |
| Trigger payload | VENDOR/CPP 9B vs LHX/HUGEL 10B | No silent merge; archive versioned golden vectors |
| Parameter payload | 0x80 Buffer, 0x40 RLE, sign magnitude threshold, 5B sample depth and trigger depth | Byte-for-byte equality on common supported settings |
| Rate mapping | 20M=6; 25M=index7 ambiguous; 500M=CPP13 vs LHX0 | Known common vectors pass; mismatches explicitly fail/skip with model notes |
| RX packets | Fragment type1/3/4/5/6 at arbitrary boundaries, malformed footer, 512B MCU reply | Parser recovers without misalignment or evidence fabrication |
| RLE and tails | count/value vectors + overflow guard; 8/12/1 tail scenarios | Requested valid depth preserved; extra bytes never treated as samples |
| Trigger alignment | 50% pre-trigger known edge and channel skew | Physical waveform aligns with reference within documented uncertainty |

`HIL_REQUIRED` procedures: [docs/HIL-TEST-PLAN.md](../HIL-TEST-PLAN.md), [docs/LOCAL-HANDOFF.md](../LOCAL-HANDOFF.md). Task-specific acceptance and exact handoff: [docs/tasks/DL16-TASK-002.md](../tasks/DL16-TASK-002.md).

## 6. Architecture decision / safety

1. **Keep CPP as the sole live hardware backend on Windows until a scoped change passes regression and local HIL**. LHX is an independent evidence source, not a new runtime dependency.
2. Do not silently switch rate indices, add 10B trigger payload, broaden USB IDs, or enable RLE/stream based on reports alone.
3. Preserve isolated offline tests, hardware probes, firmware/host version metadata, original samples and hashes; mark evidence `SOURCE_REVIEW`, `OFFLINE_TEST`, `REPORTED_HIL`, `LOCAL_HIL` separately.
4. Pinned upstream checkout is generated in ignored `external/`; changing CPP requires a reviewed, reproducible fork / patch strategy. Do not modify ignored `external/` and present it as a permanent repository change.
5. Because LHX has **no explicit LICENSE** in checked source, reproduce observed behavior through independent implementation and testing rather than copying its files.

## 7. Outstanding questions

- Is 25 MHz index 7 disabled on all DL16 firmware or only the reporter's configuration?
- Does 500 MHz really work on standard DL16 with index 0, or is the model / firmware identified differently?
- Which 9B/10B trigger schema does this device and firmware accept, and does it genuinely gate waiting for an edge?
- Does short 512B FPGA info arrive on the owner's hardware? Does CPP reject it?
- Can order-3 trigger start offset and per-channel trimming be independently validated with a shared reference signal?
- Which 1 MHz/20 MHz/100 MHz captures preserve exact frequency, duty and skew after tail removal?
- What are the calibrated channel-to-channel skew, probe delay and threshold uncertainty for the owner's 1 us use case?

Until answered, **keep status P0/SCAFFOLD / HIL_NOT_RUN**.
