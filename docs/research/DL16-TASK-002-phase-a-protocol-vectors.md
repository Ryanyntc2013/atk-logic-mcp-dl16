# DL16-TASK-002 Phase A — offline protocol vector results

**Date:** 2026-10-10
**Status:** Phase A implemented (offline, no hardware). Phase B live gates remain `HIL_NOT_RUN`.
**Reference implementation:** `tests/protocol_reference.py` (independent Python codec).
**Vectors:** `tests/test_protocol_vectors.py` (44 tests, one of which runs the optional native harness) + `tests/vectors/dl16_protocol_vectors.json`. Full suite: 61 passed.

Sources are pinned as in
[`LHX369963-dl16-cli-cross-validation-2026-10-10.md`](LHX369963-dl16-cli-cross-validation-2026-10-10.md):
CPP `gjjisadog/ATK-Logic-Mcp@5fc47744c18c99f9ad0f554a965eb8cd1160c836`,
VENDOR `alientek-openedv/atk-logic@0dff562d24436def2bec3791684f1911997b9e35`,
LHX `LHX369963/dl16-cli@8d7c209c1e3b13923620bb34cec915291a749612`.

## Vector matrix

| Vector | Status | Implementation / expectation | Test |
|---|---|---|---|
| CRC vector | **AGREE** | reflected poly `0xEDB88320`, seed 0, final XOR `0xFFFFFFFF`; `"123456789"->0xD202D277`, empty->`0xFFFFFFFF`, not zlib default | `test_crc_vector` |
| TX framing | **AGREE** | `8x00` + `0A` + `cmd,len=payload+1` + `0B` + LE CRC32 + zero pad to 2048 | `test_build_device_frame_header_and_crc`, `test_build_device_frame_length_field_tracks_payload` |
| Bank transform | **AGREE** | 4 lanes x 512B / 256 uint16; round-trips; a raw 512B short reply is **not** fed to 2048B interleave | `test_bank_transform_*` |
| Trigger nibble | **AGREE** | even=high nibble, odd=low; enable `0x8`, rising `+0x1`, falling `+0x2`; CH0 rising `0x90`, CH1 rising `0x09`, CH7 rising byte3 low `0x09` | `test_trigger_nibble_encoding` |
| Trigger payload length | **DIFF** | VENDOR/CPP = **9B** (`8 pairs + instant flag`) vs LHX/HUGEL = **10B** (`8 pairs + 2 collect bytes`). Both constructed; not merged | `test_trigger_payload_is_9_bytes_cpp`, `test_trigger_payload_9b_vs_10b_divergence` |
| Parameter payload | **AGREE** | `0x80` Buffer, `0x40` RLE, sign-magnitude 0.1V threshold, rate code, uint40 LE depth, uint40 LE trigger depth | `test_parameter_payload_bytes`, `test_parameter_payload_rle_flag_and_threshold_sign`, `test_threshold_bounds` |
| PWM output config | **AGREE** | cmd `0x17`; 200 MHz counter; half-up period/duty; channels 0..1; local live pending (DL16-TASK-004) | `test_pwm_*` |
| Rate mapping | **DIFF** | CPP `20M=6,25M=7,250M=12,500M=13`; LHX reports index 7 no-data and `500M=0` | `test_cpp_rate_mapping_common_vectors`, `test_rate_mapping_conflict_is_preserved` |
| RX packets | **AGREE** | `0A order lenLE16 payload 00 0B`; reassembled across arbitrary chunk boundaries; bad footer de-syncs and recovers | `test_rx_parser_*`, `test_parse_ack_simple_trigger_status`, `test_parse_trigger_offset_channel_byte_counts` |
| RLE and tails | **AGREE** | `(count,value)` pairs; overflow guarded; malformed odd length rejected; extra post-depth bytes never counted as samples | `test_rle_*`, `test_finalize_samples_*`, `test_apply_start_offset_byte_and_subbyte`, `test_order3_crop_decision` |
| End-to-end crop/align | **AGREE** | synthetic order-1/3/4/6 stream: order-3 crop removes only 2048B alignment padding, depth preserved, short channel flagged incomplete | `test_end_to_end_*`, `test_order3_payload_roundtrip_and_rle_flags` |
| Short-reply policy | **AGREE** | a 512B / partial reply is not fed to the 2048B 4-lane interleave (`interleave_prefix_len`) | `test_short_512b_reply_not_interleaved` |
| Multi-URB reassembly | **AGREE** | RX frames reassembled across 2048B bulk-transfer boundaries | `test_multi_urb_reassembly_across_2048_blocks` |
| Unknown rate fallback | **DIFF** | CPP silently defaults an unknown rate to 20 MHz index 6 (documented risk, not endorsed) | `test_unknown_rate_falls_back_to_20mhz_in_cpp` |
| RLE channel data + tail | **AGREE** | order-1 RLE expands then trims to requested depth; extra bytes never counted | `test_rle_channel_data_then_finalize_preserves_depth` |
| Golden artifact | **AGREE** | language-neutral `tests/vectors/dl16_protocol_vectors.json`, hash-locked | `test_golden_vectors_match_artifact` |
| CPP<->Python cross-check | **AGREE** | native harness (real `atkdl16_core`) matches the Python reference byte-for-byte on crc/trigger/parameter/bank/device-frame **and** RX reassembly + order-3 parse | `test_native_cpp_matches_python_reference` |
| Device/USB identity | **DIFF** | primary `1A86:FFCC`; LHX additionally accepts `1A86:6A6B`, `04B4:6A6A` (not merged) | matrix-only |
| Trigger gating / alignment | **UNKNOWN** | requires a physical edge plus independent timing; `HIL_REQUIRED` | Phase B |

## Optional native cross-check

Prove the pinned C++ backend agrees with the Python reference byte-for-byte:

```powershell
powershell -File scripts/bootstrap-native.ps1        # build pinned core (once)
powershell -File scripts/build-vector-harness.ps1    # build tests/native harness
.\.venv\Scripts\python.exe -m pytest tests\test_protocol_vectors.py -q
```

The harness is optional and device-free; CI without a native build skips the
cross-check (`test_native_cpp_matches_python_reference`). Set `DL16_VECTOR_HARNESS`
to an alternate executable path.

## Deliberately preserved disagreements (not reconciled)

- **R1 rate indices:** 25 MHz / 500 MHz conflict is kept as two tables; no fallback to 20 MHz was introduced.
- **R2 trigger payload:** 9B and 10B are both built; live device acceptance is unproven.
- **R5 USB IDs:** whitelist unchanged.

## Not done in Phase A

`channel_start_offsets`/order-3 crop and tail handling are covered offline, but the
live pipeline (order-3 arrival, per-channel byte counts on real bytes) and any
`COMPLETE` time-alignment claim remain Phase B / `HIL_NOT_RUN`.
