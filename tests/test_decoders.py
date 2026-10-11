import numpy as np

from dl16_mcp.artifacts import Waveform
from dl16_mcp.decoders import decode_i2c, decode_spi, decode_uart


def wf(ch, bits, rate=1_000_000):
    arr = np.asarray(bits, dtype=np.uint8)
    raw = np.packbits(arr, bitorder="little").tobytes()
    return Waveform(ch, raw, len(bits), rate, "COMPLETE", "SYNTHETIC", {})


def uart_bits(byte, spb, data_bits=8, parity=None, stop=1, invert=False):
    high, low = (0, 1) if invert else (1, 0)
    b = [high] * spb + [low] * spb
    for k in range(data_bits):
        bit = (byte >> k) & 1
        b += [(high if bit else low)] * spb
    if parity == "even":
        p = byte.bit_count() % 2
        b += [high if p else low] * spb
    elif parity == "odd":
        p = 1 - (byte.bit_count() % 2)
        b += [high if p else low] * spb
    b += [high] * spb * stop
    b += [high] * spb
    return b


def test_uart_decodes_byte_lsb_first():
    w = wf(0, uart_bits(0x55, 10))
    frames = decode_uart(w, baud_rate=100_000)
    assert len(frames) == 1
    assert frames[0]["value"] == 0x55
    assert frames[0]["stop_ok"] is True


def test_uart_even_parity_and_mismatch():
    ok = wf(0, uart_bits(0x55, 10, parity="even"))
    assert decode_uart(ok, baud_rate=100_000, parity="even")[0]["parity_ok"] is True
    # Decoding an even-parity frame as odd must flag a parity error.
    assert decode_uart(ok, baud_rate=100_000, parity="odd")[0]["parity_ok"] is False


def test_uart_noise_glitch_does_not_swallow_following_byte():
    # A one-bit false start whose stop sample lands inside a later real frame
    # must not be stored or consume the result limit. Search resumes one bit later.
    spb = 10
    bits = [1] * 30
    bits += [0] * spb                 # false start at sample 30
    bits += [1] * 20                  # idle, real start falls at sample 60
    bits += [0] * spb                 # real start
    bits += [0] * (8 * spb)           # 0x00, LSB first
    bits += [1] * spb                 # stop
    bits += [1] * spb
    frames = decode_uart(wf(0, bits), baud_rate=100_000)
    assert [frame["value"] for frame in frames] == [0x00]
    assert all(frame["parity_ok"] and frame["stop_ok"] for frame in frames)


def test_uart_parity_error_does_not_invent_extra_bytes():
    # 0x55 falls on every other bit. A real stop with bad parity must stay one
    # frame; those data edges must not become extra valid bytes.
    first = uart_bits(0x55, 10, parity="even")
    second = uart_bits(0xA5, 10, parity="odd")
    frames = decode_uart(wf(0, first + second), baud_rate=100_000, parity="odd")
    assert [(frame["value"], frame["parity_ok"], frame["stop_ok"]) for frame in frames] == [
        (0x55, False, True),
        (0xA5, True, True),
    ]
    limited = decode_uart(wf(0, first + second), baud_rate=100_000, parity="odd", limit=1)
    assert [(frame["value"], frame["parity_ok"]) for frame in limited] == [(0x55, False)]


def test_uart_noninteger_ratio_keeps_back_to_back_ascii():
    # 1 MHz / 115200 is ~8.68 samples/bit. ASCII MSB is 0, so the only highs
    # before the next start are the stop bit (often 8 samples, below ceil).
    text = "HELLO WORLD"
    sample_rate = 1_000_000
    baud = 115200
    spb = sample_rate / baud
    lead_bits = 2.0
    n = int((lead_bits + 10 * len(text) + 3) * spb) + 5
    line = np.ones(n, dtype=np.uint8)
    for i in range(n):
        t_bit = (i + 0.5) / sample_rate * baud - lead_bits
        if t_bit < 0:
            continue
        char_i = int(t_bit // 10)
        if char_i >= len(text):
            continue
        bit_pos = int(t_bit - char_i * 10)
        if bit_pos == 0:
            line[i] = 0
        elif 1 <= bit_pos <= 8:
            line[i] = (ord(text[char_i]) >> (bit_pos - 1)) & 1
    frames = decode_uart(wf(0, line.tolist(), rate=sample_rate), baud_rate=baud)
    assert "".join(chr(frame["value"]) for frame in frames) == text
    assert all(frame["parity_ok"] and frame["stop_ok"] for frame in frames)


def test_uart_mid_frame_capture_does_not_invent_bytes():
    # 0x55 toggles every bit. A slice that starts inside that byte has falling
    # edges with a full bit of high; those must not become bytes, including
    # when the next byte follows after only its stop bit.
    spb = 10

    def frame(byte):
        bits = [0] * spb
        for k in range(8):
            bits += [((byte >> k) & 1)] * spb
        bits += [1] * spb
        return bits

    stream = [1] * 20 + frame(0x55) + frame(0x41)
    mid = stream[50:]
    assert decode_uart(wf(0, mid), baud_rate=100_000) == []
    resynced = mid + [1] * (spb * 2) + frame(0x41)
    frames = decode_uart(wf(0, resynced), baud_rate=100_000)
    assert [frame["value"] for frame in frames] == [0x41]
    assert all(frame["parity_ok"] and frame["stop_ok"] for frame in frames)


def test_uart_inverted_and_two_stop_bits():
    w = wf(0, uart_bits(0x0F, 10, stop=2, invert=True))
    frames = decode_uart(w, baud_rate=100_000, stop_bits=2, invert=True)
    assert frames[0]["value"] == 0x0F
    assert frames[0]["stop_ok"] is True


def spi_bits(value, spb=4, cpol=0):
    """MSB-first 8-bit transfer; clk idles at cpol. Returns (clk, mosi)."""
    clk, mosi = [], []
    idle = cpol
    clk += [idle] * spb
    mosi += [0] * spb
    for k in range(7, -1, -1):
        bit = (value >> k) & 1
        if cpol == 0:
            clk += [1] * spb + [0] * spb
        else:
            clk += [0] * spb + [1] * spb
        mosi += [bit] * (2 * spb)
    return clk, mosi


def test_spi_mode0_msb_first():
    clk, mosi = spi_bits(0xA5, cpol=0)
    cs = [0] * len(clk)  # active low for the whole transfer
    words = decode_spi(wf(0, clk), wf(1, mosi), cs=wf(2, cs), cpol=0, cpha=0, bit_order="msb")
    assert len(words) == 1
    assert words[0]["mosi"] == 0xA5


def test_spi_lsb_first_roundtrip():
    # Same physical bits read LSB-first differ from MSB-first.
    clk, mosi = spi_bits(0x01, cpol=0)
    words = decode_spi(wf(0, clk), wf(1, mosi), cpol=0, cpha=0, bit_order="lsb")
    assert words[0]["mosi"] == 0x80


def i2c_bits(value, spb=4):
    scl, sda = [], []

    def add(sv, dv, n):
        scl.extend([sv] * n)
        sda.extend([dv] * n)

    add(1, 1, spb)          # idle
    add(1, 0, spb)          # START (SDA falls while SCL high)
    for k in range(7, -1, -1):
        bit = (value >> k) & 1
        add(0, bit, spb)    # SDA set while SCL low
        add(1, bit, spb)    # SCL high -> sampled
        add(0, bit, spb)
    add(0, 0, spb)          # ACK bit low (acknowledged)
    add(1, 0, spb)
    add(0, 0, spb)
    add(1, 0, spb)          # SCL high, SDA low
    add(1, 1, spb)          # STOP (SDA rises while SCL high)
    add(1, 1, spb)
    return scl, sda


def test_i2c_start_byte_ack_stop():
    scl, sda = i2c_bits(0xA5)
    events = decode_i2c(wf(0, scl), wf(1, sda))
    kinds = [e["type"] for e in events]
    assert kinds[0] == "start"
    assert "stop" in kinds
    byte = next(e for e in events if e["type"] == "byte")
    assert byte["value"] == 0xA5
    assert byte["ack"] is True
