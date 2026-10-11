# Upstream provenance and reuse matrix (2026-10-10)

| Project | Pin | License | How used here |
|---|---|---|---|
| [ALIENTEK atk-logic](https://github.com/alientek-openedv/atk-logic) | `0dff562d24436def2bec3791684f1911997b9e35` | GPL-3.0-or-later | USB/FPGA/trigger protocol ground truth; reference checkout only |
| [ALIENTEK atk_libsigrokdecode](https://github.com/alientek-openedv/atk_libsigrokdecode) | `783fec96047f5859c2122ac79123a6929a35f75f` | GPL-3.0-or-later | Protocol decoder catalog / architecture reference; not bundled |
| [gjjisadog ATK-Logic-Mcp](https://github.com/gjjisadog/ATK-Logic-Mcp) | `5fc47744c18c99f9ad0f554a965eb8cd1160c836` | GPL-3.0-or-later | **Actual native USB backend/CLI plus UART/SPI/I2C Python decoders**, cloned at setup time |
| [hugelzhang atk-logic-mcp](https://github.com/hugelzhang/atk-logic-mcp) | `77320addfb34d3973d09a7af663de76023034587` | MIT (project; review dependency licenses separately) | Hardware report cross-check: RLE, device self PWM, overflow artifacts, `.atkdl`, false-trigger concerns; not bundled |
| [LHX369963 dl16-cli](https://github.com/LHX369963/dl16-cli) | `8d7c209c1e3b13923620bb34cec915291a749612` | **No explicit LICENSE found** in public tree; do not copy code | Independently implemented Linux PyUSB / author-reported DL16 HIL: sampling indices, 9B/10B triggers, MCU/FPGA handshake, RLE/Stream, 512B short responses; **research only, not bundled** |

The content of these upstream repositories is **NOT copied** into this project's tracked source tree. `scripts/bootstrap-native.ps1` clones a pinned snapshot locally; this is an important distinction from claiming the entire C++ source has been independently rewritten or fully HIL-tested. `scripts/bootstrap-references.ps1` optionally fetches the remaining repos for auditors.

## Independent LHX cross-validation (2026-10-10)

See [LHX cross-validation research](research/LHX369963-dl16-cli-cross-validation-2026-10-10.md) and the [DL16-TASK-002 implementation/hardware handoff](tasks/DL16-TASK-002.md). Source code agreement is **not** HIL. Open high-risk differences: 25MHz rate index 7 versus no-data, DL16 500MHz index 0 versus current CPP index 13 / Plus-only constraints, 9B versus 10B simple trigger, 512B short handshake behavior, pre-trigger order-3 and mode-dependent trailer sizes. Published author HIL is not locally reproduced. Keep `gjjisadog` pinned as current runtime; do not adopt the third-party PyUSB implementation without licensing, explicit design review and tested patches.

## Verified by source review (not by our physical device)

- USB VID/PID `1A86:FFCC`, bulk OUT 0x02 and IN 0x81, 2048-byte four-bank reordering.
- Trigger/config command family 0x11/0x12, stop 0x15, 30ms analog threshold settling.
- Native capture state reports Order-4 ACK and Order-6 completion, sample count, `data_integrity` fields.
- The pinned native CLI's `capture` supports channels, sample rate, milliseconds, threshold, immediate or single channel trigger, buffer/experimental stream, `--json`. **It does not currently expose RLE or native timeout arguments.**
- Upstream GUI and native CLI typically both claim exclusive WinUSB access.

## Conflicting or version-dependent reports needing HIL

- hugelzhang reports trigger requests can still capture constant levels on the tested firmware; ACK is not trigger gating proof.
- hugelzhang reports all 16 channels may be transmitted despite a subset being requested; inspect actual transfers on OUR hardware before making throughput assumptions.
- hugelzhang reports post-depth residual bytes can distort frequency; bounds-truncate every channel based on actual metadata.
- Model-dependent max sample rates, trigger semantics, and RLE capacities remain to be measured locally.
- No claim is made that vendor `.atkdl` stored-file integrity equates to physical capture completeness.

## Host-side session evidence journal (DL16-TASK-020)

The optional session journal is independently implemented host-side JSONL logging, not a USB protocol implementation or translation of LHX source. It records caller declarations and native responses with their distinct authority; binary/file SHA-256 establishes byte identity, not physical authenticity or hardware acceptance. It does not retain raw USB traffic or retrospectively strengthen TASK-018 console-transcribed evidence. See [TASK-020](tasks/DL16-TASK-020-session-evidence-journal.md).

## Bounded native observations (DL16-TASK-022)

The diagnostics patch independently instruments the pinned CPP capture path and serializer without changing receive termination, USB recovery or crop behavior. Candidate stale-Complete, crop-clearing and short-response explanations remain hypotheses; neither TASK-021 timing nor the 512-byte zero MCU reply proves them. LHX lifecycle observations remain source evidence only and no LHX code was copied or translated. See [TASK-022](tasks/DL16-TASK-022-bounded-native-rx-diagnostics.md).

## Pre-arm observations (DL16-TASK-025)

The additive pre-arm patch observes the pinned CPP wake write and its existing internal flush, followed by the existing explicit capture flush. No upstream timing, limits, return behavior or protocol sequence was replaced. Flush timeout/empty results and error counters do not prove endpoint emptiness or packet generation ownership. Independent implementation and acceptance: [TASK-025](tasks/DL16-TASK-025-prearm-telemetry.md); no LHX source copied.

## Experimental depth/stop lifecycle (DL16-TASK-027)

Operator requested an independently implemented experiment based on documented LHX initialize-once, depth-based ordinary acquisition and final-stop principles. The native opt-in is not a port or compatibility claim: pinned framing/crop/marker requirements remain, no LHX source was copied/translated, and local physical validation is pending. See [TASK-027](tasks/DL16-TASK-027-experimental-depth-stop.md). Sufficient bytes/markers do not establish acquisition generation ownership.

## Single-owner PWM and failure boundary (DL16-TASK-032)

Native session PWM payloads are independently derived from this repository's reviewed TASK-004 helper and versioned PWM vectors. No new LHX code copied. The depth-stop lifecycle remains a behavioral experiment, not an exact LHX port. Dual known waveforms passed locally when configured in one Device ownership interval; timeout reuse failed and is now handled by closing the failed owner before a later explicit request. See [TASK-032](tasks/DL16-TASK-032-single-owner-long-session.md). Host stop-transfer success is not firmware acknowledgement or waveform generation authenticity.

## Offline session reliability contracts (DL16-TASK-043)

Strict protocol-1 hello validation and scripted worker reliability regressions are independently implemented from this repository's host-side JSONL ownership contract, without copying or translating third-party code. These tests cover capability isolation, timeout cleanup, explicit fresh owners and stale request rejection; they do not prove physical acquisition generation ownership. See [TASK-043](tasks/DL16-TASK-043-session-reliability.md). Evidence is CONTRACT_MOCK / OFFLINE, not HIL.

## Bounded offline raw-RX replay (DL16-TASK-046)

The repository-owned USB-free harness links the existing pinned CPP core
`gjjisadog/ATK-Logic-Mcp@5fc47744c18c99f9ad0f554a965eb8cd1160c836`
(`convert_to_pc`, `RxParser`); it does not modify ignored upstream sources.
Synthetic bank/frame vectors are independently constructed with this repository's
`tests/protocol_reference.py`; no LHX source was copied or translated.
Replay reports OFFLINE_REPLAY with UNKNOWN input provenance/integrity/completeness.
A Complete packet is only a parsed marker. Raw-RX logging metadata regressions
mock backend subprocess responses: CONTRACT_MOCK, not proof of native logging
implementation or physical USB capture. See [TASK-046](tasks/DL16-TASK-046-offline-replay.md).

## Native bounded raw-RX logging (DL16-TASK-047)

The final tracked `scripts/patches/atk-dl16-raw-rx.patch` independently instruments
pinned CPP `CaptureEngine`'s existing synchronous receive path before
`convert_to_pc`. The repository-owned framed file writer records original reads
and native status ordinals; no LHX source copied or translated, no protocol or
recovery command added. Native writer/file failure tests execute the actual C++
implementation with synthetic bytes and injected I/O failures; Python forwarding
mocks remain CONTRACT_MOCK. Fresh bootstrap application/build is offline evidence,
not HIL. Format/completeness boundaries and parent-only hardware recommendation:
[TASK-047](tasks/DL16-TASK-047-native-raw-rx-logging.md).

## License hygiene

- Keep provenance, git commit IDs and third-party NOTICE when embedding source in the future.
- GPL Python decoder distribution may have stronger obligations if integrated directly; maintain separation and attribution until legal review.
- No proprietary hardware firmware, DLLs, Windows drivers, binaries, or hidden device identifiers are committed.
