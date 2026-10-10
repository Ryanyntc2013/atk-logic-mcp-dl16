"""Independent reference codecs for the ATK-DL16 wire protocol (DL16-TASK-002 Phase A).

This module re-implements the *pure* byte-level protocol logic independently in
Python so the wire contract can be regression-tested without USB hardware and
without importing the ignored native checkout. It is derived from the documented
protocol (see docs/research/LHX369963-dl16-cli-cross-validation-2026-10-10.md)
and cross-checked against the pinned GPL-3.0 C++ backend
(gjjisadog/ATK-Logic-Mcp@5fc47744c18c99f9ad0f554a965eb8cd1160c836, same license).

It is a *reference* for tests, not a runtime backend. Discrepancies between
implementations are intentionally preserved and labelled; see MATRIX in
tests/test_protocol_vectors.py.
"""
from __future__ import annotations

import math
import struct
from dataclasses import dataclass, field

USB_BLOCK_SIZE = 2048
TX_HEADER_OFFSET = 8
TX_FRAME_START = 0x0A
TX_FRAME_END = 0x0B
RX_FRAME_START = 0x0A
RX_FRAME_END = 0x0B
RX_FRAME_SEP = 0x00
TOTAL_CHANNELS = 16

CMD_GET_DEVICE_DATA = 0x10
CMD_PARAMETER_SETTING = 0x11
CMD_SIMPLE_TRIGGER = 0x12
CMD_STOP = 0x15
CMD_PWM = 0x17

# PWM output configuration (DL16 has two PWM outputs, channels 0..1).
# Counter clock and payload layout cross-checked against LHX369963/dl16-cli
# (docs/protocol/pwm.md, pinned 8d7c209) and the original app transaction
# (1 kHz/50% -> period_count=200000, duty_count=100000). Independently implemented.
PWM_COUNTER_HZ = 200_000_000
PWM_CHANNELS = (0, 1)
PWM_FREQ_MIN_HZ = 1
PWM_FREQ_MAX_HZ = 20_000_000

# CPP sample_rate_to_code() table (pinned backend).
CPP_RATE_TO_CODE = {
    1_000_000: 1, 2_000_000: 2, 4_000_000: 3, 5_000_000: 4, 10_000_000: 5,
    20_000_000: 6, 25_000_000: 7, 40_000_000: 8, 50_000_000: 9,
    100_000_000: 10, 200_000_000: 11, 250_000_000: 12, 500_000_000: 13,
    1_000_000_000: 14,
}
CPP_CODE_TO_RATE = {v: k for k, v in CPP_RATE_TO_CODE.items()}

# LHX independent table (author-reported). Kept separate on purpose (SOURCE_CONFLICT).
LHX_RATE_TO_INDEX = {
    1_000_000: 1, 2_000_000: 2, 4_000_000: 3, 5_000_000: 4, 10_000_000: 5,
    20_000_000: 6, 40_000_000: 8, 50_000_000: 9, 100_000_000: 10,
    200_000_000: 11, 250_000_000: 12, 500_000_000: 0,
}


# --------------------------------------------------------------------------- CRC


def _build_crc_table() -> list[int]:
    table = []
    for i in range(256):
        c = i
        for _ in range(8):
            c = (0xEDB88320 ^ (c >> 1)) if (c & 1) else (c >> 1)
        table.append(c)
    return table


_CRC32_TABLE = _build_crc_table()


def compute_crc32(data: bytes) -> int:
    """Reflected poly 0xEDB88320, seed 0, final XOR 0xFFFFFFFF.

    Not zlib.crc32 default; empty input is defined as 0xFFFFFFFF.
    """
    if not data:
        return 0xFFFFFFFF
    crc = 0
    for byte in data:
        crc = _CRC32_TABLE[(crc ^ byte) & 0xFF] ^ (crc >> 8)
    return crc ^ 0xFFFFFFFF


# ---------------------------------------------------------- 4-way bank transform


def convert_to_device(pc: bytes) -> bytes:
    """PC sequential order -> FPGA 4-lane interleaved (2048B blocks)."""
    if len(pc) % USB_BLOCK_SIZE:
        raise ValueError("length must be a multiple of 2048")
    out = bytearray(len(pc))
    for base in range(0, len(pc), USB_BLOCK_SIZE):
        src = struct.unpack_from("<1024H", pc, base)
        lanes = [[0] * 256 for _ in range(4)]
        for j in range(256):
            k = 4 * j
            lanes[0][j] = src[k]
            lanes[1][j] = src[k + 1]
            lanes[2][j] = src[k + 2]
            lanes[3][j] = src[k + 3]
        for li in range(4):
            struct.pack_into("<256H", out, base + li * 512, *lanes[li])
    return bytes(out)


def convert_to_pc(dev: bytes) -> bytes:
    """FPGA 4-lane interleaved -> PC sequential order (2048B blocks)."""
    if len(dev) % USB_BLOCK_SIZE:
        raise ValueError("length must be a multiple of 2048")
    out = bytearray(len(dev))
    for base in range(0, len(dev), USB_BLOCK_SIZE):
        lanes = [struct.unpack_from("<256H", dev, base + li * 512) for li in range(4)]
        dst = [0] * 1024
        for j in range(256):
            k = 4 * j
            dst[k] = lanes[0][j]
            dst[k + 1] = lanes[1][j]
            dst[k + 2] = lanes[2][j]
            dst[k + 3] = lanes[3][j]
        struct.pack_into("<1024H", out, base, *dst)
    return bytes(out)


# --------------------------------------------------------------- frame building


def build_device_frame(code: int, payload: bytes = b"") -> bytes:
    new_code = bytes([code, (len(payload) + 1) & 0xFF]) + payload
    crc = compute_crc32(new_code)
    raw = bytearray(TX_HEADER_OFFSET)
    raw.append(TX_FRAME_START)
    raw += new_code
    raw.append(TX_FRAME_END)
    raw += struct.pack("<I", crc)
    raw += bytes((-len(raw)) % USB_BLOCK_SIZE)
    return convert_to_device(bytes(raw))


def _cpp_round_half_away_from_zero(value: float) -> int:
    return math.floor(value + 0.5) if value >= 0 else -math.floor(-value + 0.5)


def encode_threshold(voltage: float) -> int:
    b = 0x80 if voltage < 0.0 else 0x00
    rounded = max(0, min(50, _cpp_round_half_away_from_zero(abs(voltage) * 10.0)))
    return b | (rounded & 0x7F)


def decode_threshold(byte: int) -> float:
    val = (byte & 0x7F) / 10.0
    return -val if (byte & 0x80) else val


def sample_rate_to_code(rate_hz: int) -> int:
    return CPP_RATE_TO_CODE.get(rate_hz, 0)


def code_to_sample_rate(code: int) -> int:
    return CPP_CODE_TO_RATE.get(code, 0)


def cpp_rate_code_or_default(rate_hz: int, default: int = 6) -> int:
    """Mirror CPP build_parameter_setting_frame(): unknown rate silently falls back to 20 MHz.

    Documented here as a known behavior/risk, not an endorsement (see research R1 note).
    """
    code = sample_rate_to_code(rate_hz)
    return code if code else default


def interleave_prefix_len(actual_len: int) -> int:
    """capture.cpp policy: only whole 2048B blocks are bank-deinterleaved.

    A short MCU/FPGA reply (e.g. 512B) is never passed through the 4-lane transform.
    """
    return (actual_len // USB_BLOCK_SIZE) * USB_BLOCK_SIZE


def _append_uint_le(buf: bytearray, value: int, num_bytes: int) -> None:
    for i in range(num_bytes):
        buf.append((value >> (i * 8)) & 0xFF)


def parameter_payload(mode_buffer: bool, enable_rle: bool, threshold_v: float,
                      rate_code: int, sample_depth: int, trigger_depth: int) -> bytes:
    payload = bytearray()
    flags = 0
    if mode_buffer:
        flags |= 0x80
    if enable_rle:
        flags |= 0x40
    payload.append(flags)
    payload.append(encode_threshold(threshold_v))
    payload.append(rate_code)
    _append_uint_le(payload, sample_depth, 5)
    _append_uint_le(payload, trigger_depth, 5)
    return bytes(payload)


def total_samples(rate_hz: int, duration_ms: int) -> int:
    return (rate_hz // 1000) * duration_ms


def trigger_sample_index(rate_hz: int, duration_ms: int, position_percent: float) -> int:
    return int(total_samples(rate_hz, duration_ms) * (position_percent / 100.0))


_TRIGGER_BITS = {
    # (even_high_nibble, odd_low_nibble) contributions before the enable bit.
    "rising": (0x10, 0x01),
    "falling": (0x20, 0x02),
    "high": (0x40, 0x04),
    "low": (0x00, 0x00),
    "double": (0x30, 0x03),
    None: (0x70, 0x07),  # enabled but no explicit type (CPP "default")
}


def trigger_payload_cpp(enabled, triggers=None, is_instantly: bool = False) -> bytes:
    """Simple-trigger payload.

    Immediate uses the 9-byte form (8 pair bytes + instant flag). Non-immediate
    triggers use the 10-byte gating form (8 pair bytes + 2 zero collect-type bytes);
    HIL (DL16-TASK-010) shows the 9-byte form does not gate and the 10-byte form does.
    """
    enabled = set(enabled)
    triggers = triggers or {}
    out = bytearray()
    for i in range(0, TOTAL_CHANNELS, 2):
        b = 0
        if i in enabled:
            b |= 0x80
            b |= _TRIGGER_BITS[triggers.get(i)][0]
        if (i + 1) in enabled:
            b |= 0x08
            b |= _TRIGGER_BITS[triggers.get(i + 1)][1]
        out.append(b)
    if is_instantly:
        out.append(1)
    else:
        out.append(0)
        out.append(0)
    return bytes(out)


def trigger_payload_lhx(enabled, triggers=None, collect_type: int = 0) -> bytes:
    """LHX/HUGEL reported 10-byte payload: 8 pair bytes + 2 collect-type bytes.

    Constructed independently from the report (collect-type semantics unverified).
    Preserved only to make the 9B/10B divergence explicit.
    """
    eight = trigger_payload_cpp(enabled, triggers, is_instantly=True)[:8]
    return eight + bytes([collect_type & 0xFF, (collect_type >> 8) & 0xFF])


# --------------------------------------------------------- PWM output config


def _pwm_validate(channel: int, frequency_hz: int, duty_percent: float) -> None:
    if channel not in PWM_CHANNELS:
        raise ValueError("PWM channel must be 0 or 1")
    if not isinstance(frequency_hz, int) or not PWM_FREQ_MIN_HZ <= frequency_hz <= PWM_FREQ_MAX_HZ:
        raise ValueError(f"PWM frequency must be an integer in [{PWM_FREQ_MIN_HZ}, {PWM_FREQ_MAX_HZ}] Hz")
    if not 0.0 <= duty_percent <= 100.0:
        raise ValueError("PWM duty must be within [0, 100] percent")


def pwm_period_count(frequency_hz: int) -> int:
    """period_count = floor(200_000_000 / frequency_hz + 0.5) (half-up)."""
    return math.floor(PWM_COUNTER_HZ / frequency_hz + 0.5)


def pwm_duty_count(period_count: int, duty_percent: float) -> int:
    """duty_count = floor(period_count * duty_percent / 100 + 0.5) (half-up)."""
    return math.floor(period_count * duty_percent / 100.0 + 0.5)


def pwm_start_payload(channel: int, frequency_hz: int, duty_percent: float) -> bytes:
    """PWM start payload (9 bytes): [(ch<<4)+0x11][period LE u32][duty LE u32]."""
    _pwm_validate(channel, frequency_hz, duty_percent)
    period = pwm_period_count(frequency_hz)
    duty = pwm_duty_count(period, duty_percent)
    return bytes([(channel << 4) + 0x11]) + period.to_bytes(4, "little") + duty.to_bytes(4, "little")


def pwm_stop_payload(channel: int) -> bytes:
    """PWM stop payload (1 byte): [(ch + 1) << 4]."""
    if channel not in PWM_CHANNELS:
        raise ValueError("PWM channel must be 0 or 1")
    return bytes([(channel + 1) << 4])


def pwm_start_frame(channel: int, frequency_hz: int, duty_percent: float) -> bytes:
    return build_device_frame(CMD_PWM, pwm_start_payload(channel, frequency_hz, duty_percent))


def pwm_stop_frame(channel: int) -> bytes:
    return build_device_frame(CMD_PWM, pwm_stop_payload(channel))


# ------------------------------------------------------------------- RX parsing


def build_rx_frame(order: int, payload: bytes = b"") -> bytes:
    return bytes([RX_FRAME_START, order]) + struct.pack("<H", len(payload)) + payload + bytes(
        [RX_FRAME_SEP, RX_FRAME_END])


@dataclass
class RxMessage:
    order: int
    payload: bytes


class RxParser:
    """Byte-stream reassembler independent of USB chunk boundaries."""

    def __init__(self) -> None:
        self._buf = bytearray()
        self._pos = 0
        self.messages: list[RxMessage] = []
        self.desync_count = 0

    def push_bytes(self, data: bytes) -> None:
        self._buf += data
        self._process()

    def _process(self) -> None:
        n = len(self._buf)
        while self._pos < n:
            if self._buf[self._pos] != RX_FRAME_START:
                self._pos += 1
                self.desync_count += 1
                continue
            if self._pos + 4 > n:
                break
            order = self._buf[self._pos + 1]
            if order < 1 or order > 6:
                self._pos += 1
                self.desync_count += 1
                continue
            payload_len = self._buf[self._pos + 2] | (self._buf[self._pos + 3] << 8)
            total = 4 + payload_len + 2
            if self._pos + total > n:
                break
            sep = self._pos + 4 + payload_len
            if self._buf[sep] == RX_FRAME_SEP and self._buf[sep + 1] == RX_FRAME_END:
                self.messages.append(RxMessage(order, bytes(self._buf[self._pos + 4:sep])))
                self._pos += total
            else:
                self._pos += 1
                self.desync_count += 1

    def pop(self) -> RxMessage | None:
        return self.messages.pop(0) if self.messages else None


def _read_uint40_le(buf: bytes, offset: int) -> int:
    val = 0
    for i in range(5):
        val |= buf[offset + i] << (8 * i)
    return val


def parse_channel_data(msg: RxMessage, is_rle: bool = False):
    if msg.order != 1 or len(msg.payload) < 2:
        return None
    channel_id = msg.payload[0]
    raw = msg.payload[2:]
    if is_rle:
        res = decompress_rle(raw)
        if not res.success:
            return None
        return channel_id, res.data
    return channel_id, raw


def parse_trigger_offset(msg: RxMessage, channel_count: int = TOTAL_CHANNELS, is_rle: bool = False):
    if msg.order != 3 or len(msg.payload) < 7:
        return None
    p = 2
    remaining = len(msg.payload) - 2
    if remaining < 5:
        return None
    result = {"trigger_sample_offset": _read_uint40_le(msg.payload, p), "channel_byte_counts": []}
    p += 5
    remaining -= 5
    if remaining >= channel_count * 5:
        for _ in range(channel_count):
            result["channel_byte_counts"].append(_read_uint40_le(msg.payload, p))
            p += 5
        remaining -= channel_count * 5
    if is_rle and remaining >= 1:
        flags = msg.payload[p]
        result["exceed_capacity"] = bool(flags & 0x01)
        result["exceed_bandwidth"] = bool(flags & 0x02)
    return result


def parse_ack(msg: RxMessage):
    if msg.order != 4 or len(msg.payload) < 3:
        return None
    return {"command_code": msg.payload[2], "status": msg.payload[3] if len(msg.payload) > 3 else 0}


def parse_complete(msg: RxMessage, is_buffer: bool = True):
    if msg.order != 6:
        return None
    if not is_buffer and len(msg.payload) >= 3:
        return {"is_stream_capacity_exceeded": msg.payload[2] == 1}
    return {}


# ------------------------------------------------------------------------- RLE


@dataclass
class RleResult:
    success: bool
    data: bytes = b""
    error_message: str = ""


def decompress_rle(compressed: bytes, max_output_size: int = 1 << 30) -> RleResult:
    if not compressed:
        return RleResult(True, b"")
    if len(compressed) % 2 != 0:
        return RleResult(False, error_message="odd byte length")
    total = 0
    for i in range(0, len(compressed), 2):
        total += compressed[i]
        if total > max_output_size:
            return RleResult(False, error_message="expansion overflow")
    out = bytearray()
    for i in range(0, len(compressed), 2):
        out += bytes([compressed[i + 1]]) * compressed[i]
    return RleResult(True, bytes(out))


# ------------------------------------------------------------- crop / finalize


@dataclass
class ChannelStore:
    data: bytearray = field(default_factory=bytearray)
    sample_count: int = 0


def finalize_samples(store: ChannelStore, target_samples: int) -> None:
    valid = min(store.sample_count, target_samples)
    store.sample_count = valid
    target_bytes = (valid + 7) // 8
    if len(store.data) > target_bytes:
        del store.data[target_bytes:]
    remaining_bits = valid % 8
    if remaining_bits and store.data:
        store.data[-1] &= (1 << remaining_bits) - 1


def apply_start_offset(store: ChannelStore, offset_bits: int) -> None:
    orig = store.sample_count
    if offset_bits >= orig or not store.data:
        store.data = bytearray()
        store.sample_count = 0
        return
    remove_bytes = offset_bits // 8
    bit_shift = offset_bits % 8
    if remove_bytes >= len(store.data):
        store.data = bytearray()
        store.sample_count = 0
        return
    if remove_bytes:
        del store.data[:remove_bytes]
    if bit_shift and store.data:
        n = len(store.data)
        for i in range(n - 1):
            store.data[i] = ((store.data[i] >> bit_shift) | (store.data[i + 1] << (8 - bit_shift))) & 0xFF
        store.data[n - 1] >>= bit_shift
    store.sample_count = orig - offset_bits
    needed = (store.sample_count + 7) // 8
    if len(store.data) > needed:
        del store.data[needed:]


def channel_start_offset(channel_byte_count: int, target_samples: int,
                         trigger_depth: int, trigger_offset: int) -> int | None:
    """Mirror capture.cpp order-3 crop decision; None means no crop for this channel."""
    total_bits = channel_byte_count * 8
    if total_bits > target_samples and total_bits > (trigger_depth + trigger_offset):
        return total_bits - trigger_depth - trigger_offset
    return None


# ------------------------------------------------- end-to-end capture pipeline


@dataclass
class SimConfig:
    enabled_channels: tuple[int, ...] = (0, 1)
    sample_rate: int = 1_000_000
    duration_ms: int = 1
    position_percent: float = 20.0
    enable_rle: bool = False

    def total_samples(self) -> int:
        return (self.sample_rate // 1000) * self.duration_ms

    def trigger_sample_index(self) -> int:
        return int(self.total_samples() * (self.position_percent / 100.0))


@dataclass
class SimResult:
    stores: dict
    trigger_offset: int | None
    channel_start_offsets: dict
    ack_ok: bool
    complete: bool
    warnings: list


def simulate_capture(rx_bytes: bytes, config: SimConfig) -> SimResult:
    """Replay the pure parts of capture.cpp over a synthetic PC-order RX stream.

    Handles order 1 (channel data), order 3 (trigger offset + per-channel byte
    counts + crop decision), order 4 (SimpleTrigger ACK) and order 6 (complete).
    """
    parser = RxParser()
    parser.push_bytes(rx_bytes)
    stores = {ch: ChannelStore() for ch in config.enabled_channels}
    start_offsets: dict[int, int] = {}
    trigger_offset: int | None = None
    ack_ok = False
    complete = False
    warnings: list[str] = []
    target = config.total_samples()
    trig_depth = config.trigger_sample_index()
    is_rle = config.enable_rle

    for msg in parser.messages:
        if msg.order == 1:
            parsed = parse_channel_data(msg, is_rle)
            if parsed:
                ch, data = parsed
                if ch in stores:
                    stores[ch].data += data
                    stores[ch].sample_count += len(data) * 8
        elif msg.order == 3:
            t = parse_trigger_offset(msg, TOTAL_CHANNELS, is_rle)
            if t:
                trigger_offset = t["trigger_sample_offset"]
                for i, count in enumerate(t["channel_byte_counts"]):
                    off = channel_start_offset(count, target, trig_depth, trigger_offset)
                    if off is not None:
                        start_offsets[i] = off
        elif msg.order == 4:
            a = parse_ack(msg)
            if a and a["command_code"] == CMD_SIMPLE_TRIGGER and a["status"] == 3:
                ack_ok = True
            elif a:
                warnings.append(f"trigger ACK rejected status {a['status']}")
        elif msg.order == 6:
            complete = True

    for ch, off in start_offsets.items():
        if ch in stores:
            apply_start_offset(stores[ch], off)
    for ch in config.enabled_channels:
        finalize_samples(stores[ch], target)
        if stores[ch].sample_count < target:
            warnings.append(f"channel {ch} incomplete: {stores[ch].sample_count}/{target}")

    return SimResult(stores, trigger_offset, start_offsets, ack_ok, complete, warnings)


def order3_payload(trigger_sample_offset: int, channel_byte_counts: dict[int, int],
                   rle_flags: int | None = None) -> bytes:
    payload = bytearray([0, 0])
    payload += trigger_sample_offset.to_bytes(5, "little")
    for i in range(TOTAL_CHANNELS):
        payload += channel_byte_counts.get(i, 0).to_bytes(5, "little")
    if rle_flags is not None:
        payload.append(rle_flags)
    return bytes(payload)

