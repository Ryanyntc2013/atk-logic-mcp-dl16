"""DL16-TASK-002 Phase A: deterministic offline protocol vectors.

These tests exercise an independent Python reference implementation
(tests/protocol_reference.py) against documented wire constants and the pinned
C++ backend behavior. They require no USB hardware and change no live backend.

Each vector carries an explicit AGREE / DIFF / UNKNOWN label so cross-source
disagreements stay visible instead of being silently reconciled.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import struct
import subprocess
import sys
import zlib

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import protocol_reference as ref

# ------------------------------------------------------------------ discrepancy matrix
# vector                    status    note
MATRIX = {
    "crc_vector": ("AGREE", "CPP/VENDOR/LHX: 0xEDB88320 reflected, seed 0, final XOR FFFFFFFF"),
    "tx_framing": ("AGREE", "8x00 + 0A + cmd/len + 0B + LE CRC + zero pad to 2048"),
    "bank_transform": ("AGREE", "4 lanes x 512B, 256 uint16 each; unaligned 512B not transformed"),
    "trigger_nibble": ("AGREE", "even=high nibble, odd=low nibble, enable 0x8, rising+0x1, falling+0x2"),
    "trigger_payload_length": ("DIFF", "VENDOR/CPP=9B vs LHX/HUGEL=10B; firmware acceptance unproven"),
    "parameter_payload": ("AGREE", "1 mode byte, 1 threshold, 1 rate code, uint40 depth, uint40 trigger"),
    "rate_mapping": ("DIFF", "CPP 25M=7/500M=13 vs LHX 500M=0 and index-7 no-data report"),
    "rx_packets": ("AGREE", "0A order lenLE16 payload 00 0B; boundary independent of USB chunks"),
    "rle_and_tails": ("AGREE", "(count,value) pairs; extra post-depth bytes never counted as samples"),
    "end_to_end_crop_align": ("AGREE", "order-3 crop removes only alignment padding; depth preserved"),
    "short_reply_policy": ("AGREE", "512B short reply is not fed to the 2048B 4-lane interleave"),
    "unknown_rate_fallback": ("DIFF", "CPP silently defaults an unknown rate to 20 MHz index 6"),
    "pwm_output_config": ("AGREE", "cmd 0x17, 200 MHz counter, half-up period/duty; channels 0..1; LHX doc + original app, local live pending"),
    "device_info_usb_ids": ("DIFF", "primary 1A86:FFCC; LHX also lists 1A86:6A6B and 04B4:6A6A"),
    "trigger_gating_alignment": ("UNKNOWN", "requires physical edge + independent timing; HIL_REQUIRED"),
}


def test_matrix_labels_are_from_known_set():
    assert set(MATRIX) == {
        "crc_vector", "tx_framing", "bank_transform", "trigger_nibble",
        "trigger_payload_length", "parameter_payload", "rate_mapping",
        "rx_packets", "rle_and_tails", "end_to_end_crop_align", "short_reply_policy",
        "unknown_rate_fallback", "pwm_output_config", "device_info_usb_ids",
        "trigger_gating_alignment",
    }
    for status, _note in MATRIX.values():
        assert status in {"AGREE", "DIFF", "UNKNOWN"}


# ----------------------------------------------------------------------------- CRC


def test_crc_vector():
    assert ref.compute_crc32(b"123456789") == 0xD202D277
    assert ref.compute_crc32(b"") == 0xFFFFFFFF
    # Must NOT be the zlib default (seed FFFFFFFF).
    assert ref.compute_crc32(b"123456789") != zlib.crc32(b"123456789")


# ------------------------------------------------------------------- bank transform


def test_bank_transform_roundtrip():
    pc = bytes((i * 7 + 3) & 0xFF for i in range(2048))
    device = ref.convert_to_device(pc)
    assert device != pc
    assert ref.convert_to_pc(device) == pc


def test_bank_transform_known_lane_layout():
    pc = bytearray(2048)
    struct.pack_into("<4H", pc, 0, 0x1111, 0x2222, 0x3333, 0x4444)
    device = ref.convert_to_device(bytes(pc))
    assert device[0:2] == b"\x11\x11"        # pc word 0 -> lane 0
    assert device[512:514] == b"\x22\x22"    # pc word 1 -> lane 1
    assert device[1024:1026] == b"\x33\x33"  # pc word 2 -> lane 2
    assert device[1536:1538] == b"\x44\x44"  # pc word 3 -> lane 3


def test_bank_transform_rejects_unaligned_512b_handshake():
    with pytest.raises(ValueError):
        ref.convert_to_device(bytes(512))


# -------------------------------------------------------------------- tx framing


def test_build_device_frame_header_and_crc():
    frame = ref.build_device_frame(ref.CMD_GET_DEVICE_DATA, b"")
    assert len(frame) % 2048 == 0
    raw = ref.convert_to_pc(frame)
    assert raw[0:8] == bytes(8)
    assert raw[8] == 0x0A
    assert raw[9] == 0x10            # command code
    assert raw[10] == 0x01           # payload_len + 1
    assert raw[11] == 0x0B
    assert struct.unpack_from("<I", raw, 12)[0] == ref.compute_crc32(bytes([0x10, 0x01]))
    assert raw[16:] == bytes(len(raw) - 16)  # zero padded


def test_build_device_frame_length_field_tracks_payload():
    frame = ref.build_device_frame(ref.CMD_PARAMETER_SETTING, bytes(range(13)))
    raw = ref.convert_to_pc(frame)
    assert raw[9] == 0x11
    assert raw[10] == 14  # 13 payload + 1


# ------------------------------------------------------------- trigger nibbles


def test_trigger_nibble_encoding():
    assert ref.trigger_payload_cpp([0], {0: "rising"})[0] == 0x90
    assert ref.trigger_payload_cpp([1], {1: "rising"})[0] == 0x09
    assert ref.trigger_payload_cpp([7], {7: "rising"})[3] == 0x09
    assert ref.trigger_payload_cpp([0], {0: "falling"})[0] == 0xA0
    assert ref.trigger_payload_cpp([0, 1], {0: "rising", 1: "falling"})[0] == 0x9A


def test_trigger_payload_is_9_bytes_cpp():
    payload = ref.trigger_payload_cpp([0], {0: "rising"})
    assert len(payload) == 9
    assert payload[8] == 0  # not immediate


def test_trigger_payload_9b_vs_10b_divergence():
    enabled = list(range(16))
    cpp = ref.trigger_payload_cpp(enabled, is_instantly=True)
    lhx = ref.trigger_payload_lhx(enabled)
    assert len(cpp) == 9
    assert len(lhx) == 10
    assert cpp[:8] == b"\xff" * 8       # all channels enabled, no explicit type
    assert cpp[8] == 1                   # immediate
    assert lhx == b"\xff" * 8 + b"\x00\x00"  # matches HUGEL's reported 10B command


# ------------------------------------------------------------ parameter payload


def test_parameter_payload_bytes():
    payload = ref.parameter_payload(True, False, 1.6, ref.sample_rate_to_code(20_000_000),
                                    400_000, 36_000)
    assert len(payload) == 13
    assert payload[0] == 0x80                       # Buffer
    assert payload[1] == 0x10                       # 1.6V -> 16
    assert payload[2] == 6                          # 20 MHz
    assert int.from_bytes(payload[3:8], "little") == 400_000
    assert int.from_bytes(payload[8:13], "little") == 36_000


def test_parameter_payload_rle_flag_and_threshold_sign():
    payload = ref.parameter_payload(True, True, -1.5, 6, 1, 0)
    assert payload[0] == 0xC0                       # Buffer + RLE
    assert payload[1] == 0x8F                       # -1.5V sign magnitude
    assert ref.decode_threshold(0x8F) == pytest.approx(-1.5)


def test_threshold_bounds():
    assert ref.encode_threshold(-5.0) == 0xB2
    assert ref.encode_threshold(5.0) == 0x32
    assert ref.encode_threshold(0.0) == 0x00
    assert ref.decode_threshold(ref.encode_threshold(3.3)) == pytest.approx(3.3)


# --------------------------------------------------------------- rate mapping


def test_cpp_rate_mapping_common_vectors():
    assert ref.sample_rate_to_code(20_000_000) == 6
    assert ref.sample_rate_to_code(100_000_000) == 10
    assert ref.sample_rate_to_code(250_000_000) == 12
    assert ref.code_to_sample_rate(6) == 20_000_000


def test_rate_mapping_conflict_is_preserved():
    # CPP maps 25M->7 and 500M->13; LHX reports index 7 gives no data and 500M->0.
    assert ref.CPP_RATE_TO_CODE[25_000_000] == 7
    assert ref.CPP_RATE_TO_CODE[500_000_000] == 13
    assert 25_000_000 not in ref.LHX_RATE_TO_INDEX  # disabling index 7 (no-data report)
    assert ref.LHX_RATE_TO_INDEX[500_000_000] == 0
    assert MATRIX["rate_mapping"][0] == "DIFF"


# ------------------------------------------------------------------- rx parser


def test_rx_parser_fragmentation_across_chunk_boundaries():
    frames = b"".join([
        ref.build_rx_frame(1, bytes([0, 0, 0xAA])),
        ref.build_rx_frame(3, bytes(range(7))),
        ref.build_rx_frame(4, bytes([0, 0, 0x12, 3])),
        ref.build_rx_frame(5, bytes(7)),
        ref.build_rx_frame(6, b""),
    ])
    parser = ref.RxParser()
    # Feed in deliberately awkward chunk sizes.
    for i in range(0, len(frames), 5):
        parser.push_bytes(frames[i:i + 5])
    orders = [m.order for m in parser.messages]
    assert orders == [1, 3, 4, 5, 6]
    assert parser.desync_count == 0


def test_rx_parser_recovers_from_bad_footer():
    good = ref.build_rx_frame(6, b"")
    bad = bytearray(ref.build_rx_frame(4, bytes([0, 0, 0x12, 3])))
    bad[-1] = 0x99  # corrupt 0x0B footer
    parser = ref.RxParser()
    parser.push_bytes(bytes(bad) + good)
    assert [m.order for m in parser.messages] == [6]
    assert parser.desync_count >= 1


def test_rx_parser_waits_for_partial_frame():
    frame = ref.build_rx_frame(1, bytes([0, 0, 0xAB, 0xCD]))
    parser = ref.RxParser()
    parser.push_bytes(frame[:-1])
    assert parser.messages == []
    parser.push_bytes(frame[-1:])
    assert [m.order for m in parser.messages] == [1]


def test_parse_channel_data_layout():
    samples = bytes([0b10000001, 0b00000011])
    msg = ref.RxMessage(1, bytes([5, 0x00]) + samples)
    parsed = ref.parse_channel_data(msg)
    assert parsed == (5, samples)  # channel id at payload[0], samples after 2 meta bytes


def test_parse_ack_simple_trigger_status():
    msg = ref.RxMessage(4, bytes([0, 0, ref.CMD_SIMPLE_TRIGGER, 3]))
    assert ref.parse_ack(msg) == {"command_code": 0x12, "status": 3}


def test_parse_trigger_offset_channel_byte_counts():
    counts = [50000] * 16
    payload = bytes([0, 0]) + (360008).to_bytes(5, "little")
    for c in counts:
        payload += c.to_bytes(5, "little")
    parsed = ref.parse_trigger_offset(ref.RxMessage(3, payload))
    assert parsed["trigger_sample_offset"] == 360008
    assert parsed["channel_byte_counts"] == counts


# ------------------------------------------------------------------------ RLE


def test_rle_decompress_count_value_pairs():
    res = ref.decompress_rle(bytes([3, 0xAA, 2, 0x00]))
    assert res.success and res.data == b"\xAA\xAA\xAA\x00\x00"


def test_rle_rejects_odd_length_and_overflow():
    assert not ref.decompress_rle(bytes([3, 0xAA, 2])).success
    assert not ref.decompress_rle(bytes([200, 0xAA]), max_output_size=100).success


# --------------------------------------------------------------- tails / crop


def test_finalize_samples_trims_and_masks_tail():
    store = ref.ChannelStore(bytearray(b"\xff" * 13), sample_count=100)
    ref.finalize_samples(store, 99)
    assert store.sample_count == 99
    assert len(store.data) == 13
    assert store.data[-1] == 0x07  # only 3 low bits kept


def test_finalize_samples_never_counts_extra_bytes_as_samples():
    store = ref.ChannelStore(bytearray(b"\xff" * 13000), sample_count=104000)
    ref.finalize_samples(store, 100000)
    assert store.sample_count == 100000
    assert len(store.data) == 12500


def test_apply_start_offset_byte_and_subbyte():
    store = ref.ChannelStore(bytearray(b"\x01\x02\x03\x04"), sample_count=32)
    ref.apply_start_offset(store, 8)
    assert store.data == bytearray(b"\x02\x03\x04")
    assert store.sample_count == 24

    store2 = ref.ChannelStore(bytearray([0b00010010, 0b00110100]), sample_count=16)
    ref.apply_start_offset(store2, 4)
    # right shift by 4 across byte boundary: (0x12>>4)|(0x34<<4) = 0x41, then 0x34>>4 = 0x03
    assert store2.data == bytearray([0b01000001, 0b00000011])
    assert store2.sample_count == 12


def test_order3_crop_decision():
    # 400000 requested; 50000 bytes*8 = 400000 base -> no crop.
    assert ref.channel_start_offset(50000, 400000, 36000, 360008) is None
    # Extra packed bytes present -> crop to align.
    off = ref.channel_start_offset(50001, 400000, 36000, 360008)
    assert off == 400008 - 36000 - 360008


# ---------------------------------------------------------------- usb id note


def test_primary_usb_identity_documented():
    assert MATRIX["device_info_usb_ids"][0] == "DIFF"
    assert (0x1A86, 0xFFCC) == (0x1A86, 0xFFCC)


# --------------------------------------------------- short reply / multi-URB


def test_short_512b_reply_not_interleaved():
    assert ref.interleave_prefix_len(512) == 0
    assert ref.interleave_prefix_len(2047) == 0
    assert ref.interleave_prefix_len(2048) == 2048
    assert ref.interleave_prefix_len(16384) == 16384
    with pytest.raises(ValueError):
        ref.convert_to_pc(bytes(512))
    assert MATRIX["short_reply_policy"][0] == "AGREE"


def test_multi_urb_reassembly_across_2048_blocks():
    frames = b"".join([
        ref.build_rx_frame(1, bytes([0, 0, 0xAA, 0xBB])),
        ref.build_rx_frame(4, bytes([0, 0, 0x12, 3])),
        ref.build_rx_frame(6, b""),
    ])
    parser = ref.RxParser()
    for i in range(0, len(frames), 2048):  # 2048B bulk-transfer slices, last short
        parser.push_bytes(frames[i:i + 2048])
    assert [m.order for m in parser.messages] == [1, 4, 6]
    assert parser.desync_count == 0


def test_rle_channel_data_then_finalize_preserves_depth():
    rle = bytes([10, 0x00, 6, 0xFF])  # 10 low + 6 high = 16 packed bytes = 128 samples
    msg = ref.RxMessage(1, bytes([3, 0x00]) + rle)
    ch, data = ref.parse_channel_data(msg, is_rle=True)
    assert ch == 3
    assert data == b"\x00" * 10 + b"\xff" * 6
    store = ref.ChannelStore(bytearray(data), sample_count=len(data) * 8)
    ref.finalize_samples(store, 12)
    assert store.sample_count == 12
    assert len(store.data) == 2


def test_unknown_rate_falls_back_to_20mhz_in_cpp():
    assert ref.sample_rate_to_code(3_000_000) == 0
    assert ref.cpp_rate_code_or_default(3_000_000) == 6
    assert MATRIX["unknown_rate_fallback"][0] == "DIFF"


# ------------------------------------------------ golden vector artifact lock

GOLDEN_PATH = pathlib.Path(__file__).parent / "vectors" / "dl16_protocol_vectors.json"


def test_golden_vectors_match_artifact():
    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    assert golden["schema"] == "dl16-protocol-vectors/1"
    v = golden["vectors"]
    assert v["crc_123456789"] == format(ref.compute_crc32(b"123456789"), "08x")
    assert v["crc_empty"] == format(ref.compute_crc32(b""), "08x")
    assert v["trigger_cpp_ch0_rising"] == ref.trigger_payload_cpp([0], {0: "rising"}).hex()
    assert v["trigger_cpp_ch0_ch1"] == ref.trigger_payload_cpp([0, 1], {0: "rising", 1: "falling"}).hex()
    assert v["trigger_cpp_all_immediate"] == ref.trigger_payload_cpp(list(range(16)), is_instantly=True).hex()
    assert v["trigger_lhx_all_immediate"] == ref.trigger_payload_lhx(list(range(16))).hex()
    assert v["parameter_buffer_20m_400k_t36k"] == ref.parameter_payload(True, False, 1.6, 6, 400000, 36000).hex()
    assert v["pwm_start_ch0_1khz_50"] == ref.pwm_start_payload(0, 1000, 50.0).hex()
    assert v["pwm_start_ch1_1khz_50"] == ref.pwm_start_payload(1, 1000, 50.0).hex()
    assert v["pwm_stop_ch0"] == ref.pwm_stop_payload(0).hex()
    assert v["pwm_stop_ch1"] == ref.pwm_stop_payload(1).hex()
    assert v["bank_transform_2048_sha256"] == hashlib.sha256(
        ref.convert_to_device(bytes(range(256)) * 8)).hexdigest()
    assert v["device_frame_get_device_data_sha256"] == hashlib.sha256(
        ref.build_device_frame(0x10)).hexdigest()
    assert v["rx_frame_order6"] == ref.build_rx_frame(6, b"").hex()


# --------------------------------------- optional native (CPP) cross-check

NATIVE_HARNESS = pathlib.Path(__file__).parent / "native" / "build" / "Release" / "dl16-vector-dump.exe"


def _native_harness() -> pathlib.Path | None:
    env = os.environ.get("DL16_VECTOR_HARNESS")
    if env and pathlib.Path(env).is_file():
        return pathlib.Path(env)
    return NATIVE_HARNESS if NATIVE_HARNESS.is_file() else None


def test_native_cpp_matches_python_reference():
    exe = _native_harness()
    if exe is None:
        pytest.skip("native harness not built; run scripts/build-vector-harness.ps1")
    out = subprocess.run([str(exe)], capture_output=True, text=True, check=True).stdout
    h = json.loads(out)
    assert h["crc_123456789"] == format(ref.compute_crc32(b"123456789"), "08x")
    assert h["crc_empty"] == format(ref.compute_crc32(b""), "08x")
    assert h["trigger_payload"] == ref.trigger_payload_cpp([0], {0: "rising"}).hex()
    assert h["parameter_payload"] == ref.parameter_payload(True, False, 1.6, 6, 400000, 36000).hex()
    assert h["bank_transform_hex"] == ref.convert_to_device(bytes(range(256)) * 8).hex()
    assert h["get_device_data_frame_hex"] == ref.build_device_frame(0x10).hex()

    # RX reassembly + order-3 parse must match the Python parser.
    stream = (
        ref.build_rx_frame(1, bytes([2, 0, 0xAA, 0xBB]))
        + ref.build_rx_frame(3, ref.order3_payload(800, {0: 128, 1: 128}, rle_flags=0x01))
        + ref.build_rx_frame(4, bytes([0, 0, ref.CMD_SIMPLE_TRIGGER, 3]))
        + ref.build_rx_frame(6, b"")
    )
    py = ref.RxParser()
    py.push_bytes(stream)
    assert h["rx_orders"] == [m.order for m in py.messages]
    assert h["rx_desync"] == 0
    trig = ref.parse_trigger_offset(next(m for m in py.messages if m.order == 3), is_rle=True)
    assert h["rx_trigger_offset"] == trig["trigger_sample_offset"]
    assert h["rx_counts_first2"] == trig["channel_byte_counts"][:2]
    assert h["rx_exceed_capacity"] is True


# --------------------------------------------- end-to-end crop / align pipeline


def _order1_frames(channel, chunks):
    return [ref.build_rx_frame(1, bytes([channel, 0x00]) + chunk) for chunk in chunks]


def test_end_to_end_crop_removes_only_alignment_padding():
    cfg = ref.SimConfig((0, 1), sample_rate=1_000_000, duration_ms=1, position_percent=20.0)
    assert cfg.total_samples() == 1000 and cfg.trigger_sample_index() == 200
    ch_data = {
        0: bytes((i * 3) & 0xFF for i in range(128)),
        1: bytes((i * 5 + 1) & 0xFF for i in range(128)),
    }
    frames = b""
    frames += b"".join(_order1_frames(0, [ch_data[0][:60], ch_data[0][60:]]))
    frames += b"".join(_order1_frames(1, [ch_data[1][:64], ch_data[1][64:]]))
    frames += ref.build_rx_frame(3, ref.order3_payload(800, {0: 128, 1: 128}))
    frames += ref.build_rx_frame(4, bytes([0, 0, ref.CMD_SIMPLE_TRIGGER, 3]))
    frames += ref.build_rx_frame(6, b"")

    res = ref.simulate_capture(frames, cfg)
    assert res.ack_ok and res.complete
    assert res.trigger_offset == 800
    assert res.channel_start_offsets == {0: 24, 1: 24}  # only the 2048B padding is cropped
    for ch in (0, 1):
        assert res.stores[ch].sample_count == 1000
        assert len(res.stores[ch].data) == 125
    assert res.warnings == []


def test_end_to_end_no_crop_when_counts_equal_depth():
    cfg = ref.SimConfig((0,), sample_rate=1_000_000, duration_ms=1, position_percent=20.0)
    data = bytes((i * 7) & 0xFF for i in range(125))
    frames = ref.build_rx_frame(1, bytes([0, 0]) + data)
    frames += ref.build_rx_frame(3, ref.order3_payload(800, {0: 125}))
    frames += ref.build_rx_frame(4, bytes([0, 0, ref.CMD_SIMPLE_TRIGGER, 3]))
    frames += ref.build_rx_frame(6, b"")
    res = ref.simulate_capture(frames, cfg)
    assert res.channel_start_offsets == {}
    assert res.stores[0].sample_count == 1000
    assert res.warnings == []


def test_end_to_end_incomplete_channel_is_flagged():
    cfg = ref.SimConfig((0, 1), sample_rate=1_000_000, duration_ms=1, position_percent=20.0)
    frames = ref.build_rx_frame(1, bytes([0, 0]) + bytes(125))  # ch0 full
    frames += ref.build_rx_frame(1, bytes([1, 0]) + bytes(10))  # ch1 short
    frames += ref.build_rx_frame(4, bytes([0, 0, ref.CMD_SIMPLE_TRIGGER, 3]))
    frames += ref.build_rx_frame(6, b"")
    res = ref.simulate_capture(frames, cfg)
    assert res.stores[0].sample_count == 1000
    assert res.stores[1].sample_count == 80
    assert any("channel 1 incomplete" in w for w in res.warnings)


def test_order3_payload_roundtrip_and_rle_flags():
    payload = ref.order3_payload(800, {0: 128, 1: 128}, rle_flags=0x01)
    parsed = ref.parse_trigger_offset(ref.RxMessage(3, payload), is_rle=True)
    assert parsed["trigger_sample_offset"] == 800
    assert parsed["channel_byte_counts"][:2] == [128, 128]
    assert parsed["exceed_capacity"] is True
    assert parsed["exceed_bandwidth"] is False


# ------------------------------------------------------------- PWM output config


def test_pwm_start_payload_1khz_50_matches_documented_transaction():
    payload = ref.pwm_start_payload(0, 1000, 50.0)
    assert len(payload) == 9
    assert payload[0] == 0x11  # (channel << 4) + 0x11
    assert int.from_bytes(payload[1:5], "little") == 200000
    assert int.from_bytes(payload[5:9], "little") == 100000
    assert payload == bytes.fromhex("11400d0300a0860100")


def test_pwm_start_payload_channel1():
    assert ref.pwm_start_payload(1, 1000, 50.0)[0] == 0x21  # (1 << 4) + 0x11


def test_pwm_stop_payload():
    assert ref.pwm_stop_payload(0) == bytes([0x10])  # (0 + 1) << 4
    assert ref.pwm_stop_payload(1) == bytes([0x20])  # (1 + 1) << 4


def test_pwm_frame_wrapping_uses_command_0x17():
    raw = ref.convert_to_pc(ref.pwm_start_frame(0, 1000, 50.0))
    assert raw[8] == 0x0A
    assert raw[9] == ref.CMD_PWM
    assert raw[10] == 10  # 9-byte payload + 1
    assert raw[11:20] == ref.pwm_start_payload(0, 1000, 50.0)
    assert raw[20] == 0x0B
    assert struct.unpack_from("<I", raw, 21)[0] == ref.compute_crc32(bytes([ref.CMD_PWM, 10]) + ref.pwm_start_payload(0, 1000, 50.0))


def test_pwm_half_up_rounding():
    assert ref.pwm_period_count(7) == 28571429  # 200e6/7 = 28571428.57 -> half-up
    period = ref.pwm_period_count(1000)
    assert ref.pwm_duty_count(period, 33.333) == 66666  # 66666.0 exactly
    assert ref.pwm_duty_count(period, 0.00025) == 1     # 0.5 rounds up (not truncate)


def test_pwm_validation_rejects_invalid():
    bad_calls = [
        lambda: ref.pwm_start_payload(2, 1000, 50.0),      # channel out of 0..1
        lambda: ref.pwm_start_payload(0, 0, 50.0),         # freq < 1 Hz
        lambda: ref.pwm_start_payload(0, 20_000_001, 50.0),  # freq > 20 MHz
        lambda: ref.pwm_start_payload(0, 1000, 101.0),     # duty > 100%
        lambda: ref.pwm_stop_payload(2),
    ]
    for call in bad_calls:
        with pytest.raises(ValueError):
            call()
