# Upstream provenance and reuse matrix (2026-10-10)

## TASK-054 Order3 offline discriminator provenance

`src/dl16_mcp/order3_diagnostics.py` is an independently authored bounded
layout/range diagnostic; it copies no third-party implementation. It preserves
raw bytes and uint40 fields, reports signed40 only as a named hypothesis, and
never returns a crop. Buffer byte-count convention remains explicitly scoped;
Stream units, tails, alignment and validity remain UNKNOWN. Versioned regression
inputs reference the TASK051/052/053 observations, not new hardware evidence.


## TASK-052 mode-specific units and diagnostic TX provenance

Pinned VENDOR `pv/thread/thread_work.cpp` at
`0dff562d24436def2bec3791684f1911997b9e35` lines230–278 reads Order3 counts as bytes
**only in Buffer mode**. CPP `rx_parser.cpp` names them bytes for all modes;
`capture.cpp` multiplies by8. This source scope difference does not establish
Stream units: TASK051 fields25001 and50016 stored bytes cannot choose between
fixed16 extras,32-byte rounding or candidate word-count-plus14. Exact16 AA suffix
is an archived observation, not a sentinel/strip contract. No LHX code copied.
Independent executable alternatives/tests retain UNKNOWN/null crop. Diagnostic
records exact host-constructed parameter/trigger transport and linear bytes plus
cached open-query device profile, not wire-observed TX or HIL acceptance; no new
USB query/protocol behavior. See [TASK052](tasks/DL16-TASK-052-stream-units-hypotheses.md)
for pinned links, hashes, focused tests and bounded parent-only10/30ms proposal.

## TASK-053 cross-depth observation provenance

Parent depth10/30ms archives have25008/75008 bytes on all16 channels,8AA suffixes;
prior20ms has50016/16AA. Fixed16/round32/universal8 rules are contradicted.
Order3 raw40 fields2^40-16 /2^40-8 are preserved, signed hypotheses not established
units. `field*2+6` also fails20ms arithmetic. New versioned sanitized profiles and
bounded read-only reproducer verify stored channels and host-constructed TX CRC;
HOST_CONSTRUCTED_NOT_BUS_OBSERVED and cached profile authority kept distinct.
No LHX borrowing or crop/COMPLETE/HIL_PASS claim; see TASK053 report for next gate.

## TASK-051 parent Stream observation provenance

`tests/vectors/task051-stream-observation-v1.json` stores sanitized exact counts,
metadata fragments and hashes from parent-provided stream-02; UNKNOWN alignment,
tails and validity. Native replay and independently authored existing Python
reference reconstruct all16 channels exactly,50016 bytes each, including16 AA
suffix bytes; this differs from approximate LHX ~8-byte Stream report. All16
matches a prior HUGEL source-reported possibility, not a verified selection rule.
No copying from LHX, no tail removal, no HIL_PASS or public Stream promotion.
`tests/task051_observation.py` only reads bounded archives; child ran offline only.

## TASK-051 internal Stream evidence probe

`tests/native/stream_evidence.cpp` is independently authored against pinned CPP
`5fc47744c18c99f9ad0f554a965eb8cd1160c836` public Device/transport, parameter/trigger/
Stop builders, RxParser and TASK-047 RawRxWriter. Uses documented Stream mode flag
(clear Buffer/RLE bits), immediate existing 9-byte trigger and existing PWM helper.
No LHX code copied/translated; TASK-002 R4 approximate tails remain REPORTED_HIL,
not a stripping contract. All received payload bytes retained, UNKNOWN uncropped
artifacts, no public Stream integration/capability or COMPLETE promotion. See
[TASK-051 bounds and parent invocation](tasks/DL16-TASK-051-stream-evidence-probe.md).

## TASK-050 incremental packed storage boundary

Independently authored native storage header is persisted as the tracked bootstrap
patch `scripts/patches/atk-dl16-incremental-writer.patch`. It uses C++ standard
filesystem/streams, not LHX implementation code. Tail evidence remains the pinned
TASK-002 R4 review: LHX `8d7c209c1e3b13923620bb34cec915291a749612` reports approximate
Stream/Buffer/RLE extras (~8/~12/~1 expanded bytes), not validated removal rules.
`tests/vectors/task050-tail-preservation-v1.json` independently constructs those
candidate excesses and verifies preserve-all UNKNOWN/INCOMPLETE behavior in the
actual native writer. No bytes removed, no live Stream capability or local HIL
claim; no third-party copying/translation. See
[TASK-050 scope and evidence](tasks/DL16-TASK-050-incremental-packed-foundation.md).


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


## Offline raw-RX container replay (DL16-TASK-048)

The `dl16-raw-rx-v1` reader independently parses TASK-047's documented framing
(`DL16RX01`, LE32 length and native status ordinal per original read) and reuses
the repository-owned pinned core's `convert_to_pc` / `RxParser`; no third-party
code was copied or translated. Each record is processed independently; only its
aligned bank prefix reaches conversion, and discarded tails/status errors are
reported. Synthetic actual-executable tests are OFFLINE_SYNTHETIC. Replay of
`artifacts/hil/DL16-TASK-047/physical/rx.bin` is OFFLINE_REPLAY: a parent-provided
archived artifact, not new HIL. Parsed Complete is not completeness proof, and no
channel comparison equivalence is claimed without crop alignment. See
[TASK-048](tasks/DL16-TASK-048-offline-raw-rx-replay.md).

## TASK-049 asynchronous BUFFER provenance

Owner dispatcher and host API independently authored against pinned CPP public interfaces and existing tracked patches. Native CaptureEngine/SampleStore adaptations persist as the final tracked bootstrap patch; no LHX implementation copied or translated. CPP Stream mode flags are not evidence of validated incremental Stream or mode-tail handling. Only async_buffer_v1 is advertised, with OFFLINE_SYNTHETIC dispatcher/native artifact evidence. Parent-provided physical cancellation requests exposed legacy OK cancellation classification; the independent shared classification fix and actual native serialization regression are SYNTHETIC_OFFLINE, not post-fix HIL. Original physical records remain unchanged; corrected-code physical cancel and Stream remain separate gates. See tasks/DL16-TASK-049-async-buffer-foundation.md.
