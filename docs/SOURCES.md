# Upstream provenance and reuse matrix (2026-10-10)

| Project | Pin | License | How used here |
|---|---|---|---|
| [ALIENTEK atk-logic](https://github.com/alientek-openedv/atk-logic) | `0dff562d24436def2bec3791684f1911997b9e35` | GPL-3.0-or-later | USB/FPGA/trigger protocol ground truth; reference checkout only |
| [ALIENTEK atk_libsigrokdecode](https://github.com/alientek-openedv/atk_libsigrokdecode) | `783fec96047f5859c2122ac79123a6929a35f75f` | GPL-3.0-or-later | Protocol decoder catalog / architecture reference; not bundled |
| [gjjisadog ATK-Logic-Mcp](https://github.com/gjjisadog/ATK-Logic-Mcp) | `5fc47744c18c99f9ad0f554a965eb8cd1160c836` | GPL-3.0-or-later | **Actual native USB backend/CLI plus UART/SPI/I2C Python decoders**, cloned at setup time |
| [hugelzhang atk-logic-mcp](https://github.com/hugelzhang/atk-logic-mcp) | `77320addfb34d3973d09a7af663de76023034587` | MIT (project; review dependency licenses separately) | Hardware report cross-check: RLE, device self PWM, overflow artifacts, `.atkdl`, false-trigger concerns; not bundled |

The content of these upstream repositories is **NOT copied** into this project's tracked source tree. `scripts/bootstrap-native.ps1` clones a pinned snapshot locally; this is an important distinction from claiming the entire C++ source has been independently rewritten or fully HIL-tested. `scripts/bootstrap-references.ps1` optionally fetches the remaining repos for auditors.

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

## License hygiene

- Keep provenance, git commit IDs and third-party NOTICE when embedding source in the future.
- GPL Python decoder distribution may have stronger obligations if integrated directly; maintain separation and attribution until legal review.
- No proprietary hardware firmware, DLLs, Windows drivers, binaries, or hidden device identifiers are committed.
