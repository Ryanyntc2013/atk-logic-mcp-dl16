"""Offline protocol decoders (UART / SPI / I2C).

Independent in-repository implementations (no USB, native code or external
checkout required) so ``logic_decode`` works offline and in CI. Design and
edge-cases are informed by the pinned upstream and sigrok behavior, but no
third-party source is copied. Reconstructed bytes are analysis output, not a
hardware attestation.
"""
from __future__ import annotations

from typing import Any

import numpy as np

from .analysis import AnalysisError
from .artifacts import Waveform

_UART_PARITY = {"none", "even", "odd"}
_SPI_BIT_ORDERS = {"msb", "lsb"}


def _bits(wave: Waveform) -> np.ndarray:
    return np.unpackbits(np.frombuffer(wave.raw, dtype=np.uint8),
                         bitorder="little")[:wave.samples].astype(bool)


def _shared_rate(waves: list[Waveform]) -> float:
    rates = {w.sample_rate_hz for w in waves}
    if len(rates) != 1:
        raise AnalysisError("Decoder channels must share a sample rate")
    return rates.pop()


def decode_uart(wave: Waveform, *, baud_rate: int = 115200, data_bits: int = 8,
                parity: str = "none", stop_bits: int = 1, invert: bool = False,
                limit: int = 1000) -> list[dict[str, Any]]:
    """Asynchronous UART frames from one channel.

    Idle is high (low when ``invert``). Each frame is sampled at bit centers.
    A valid stop bit consumes the frame even when parity fails. A failed stop
    is not returned and does not use the result limit; the search resumes one
    bit later. A start must leave idle-high, but only about half a bit is
    required, and never more than one quantized bit, so a short stop still
    qualifies before the next byte.
    """
    if baud_rate <= 0:
        raise AnalysisError("baud_rate must be positive")
    if not 5 <= data_bits <= 9:
        raise AnalysisError("data_bits must be 5..9")
    if parity not in _UART_PARITY:
        raise AnalysisError("parity must be none/even/odd")
    if stop_bits not in (1, 2):
        raise AnalysisError("stop_bits must be 1 or 2")
    if not 1 <= limit <= 10000:
        raise AnalysisError("limit must be 1..10000")
    line = _bits(wave) ^ bool(invert)  # idle high
    n = line.size
    if n < 2:
        return []
    samples_per_bit = wave.sample_rate_hz / baud_rate
    if not np.isfinite(samples_per_bit) or samples_per_bit < 2:
        raise AnalysisError("UART requires at least two samples per bit")
    parity_bits = 0 if parity == "none" else 1
    frame_bits = 1 + data_bits + parity_bits + stop_bits
    bit_width = max(1, int(np.ceil(samples_per_bit)))
    # ceil(samples_per_bit) is wider than a stop bit that quantizes to
    # floor(samples_per_bit) samples. Half a bit shows the line was idle, and
    # the check never asks for more highs than one whole quantized bit.
    idle_need = min(
        max(1, int(np.floor(samples_per_bit))),
        max(1, int(np.floor(samples_per_bit / 2.0))),
    )
    falling = np.flatnonzero(line[:-1] & ~line[1:]) + 1
    frames: list[dict[str, Any]] = []
    next_frame_start = 0
    for start in falling:
        if start < next_frame_start:
            continue  # An edge inside the preceding frame is a data bit, not a new start.
        # A start bit is a fall out of idle. A full ceil(bit) of highs rejects
        # back-to-back ASCII, whose stop bit is only ~samples_per_bit wide.
        if start < idle_need or not bool(np.all(line[start - idle_need:start])):
            continue
        centers = np.round(start + (np.arange(frame_bits) + 0.5) * samples_per_bit).astype(int)
        if centers[-1] >= n:
            break
        values = line[centers]
        if values[0]:
            continue  # start bit not low
        data = values[1:1 + data_bits]
        value = int(sum(int(bit) << k for k, bit in enumerate(data)))
        ones = int(np.count_nonzero(data))
        if parity == "even":
            parity_ok = int(values[1 + data_bits]) == (ones % 2)
        elif parity == "odd":
            parity_ok = int(values[1 + data_bits]) == (1 - (ones % 2))
        else:
            parity_ok = True
        stop_ok = bool(np.all(values[1 + data_bits + parity_bits:]))
        if stop_ok:
            # Stop defines the frame even when parity fails. Consuming it keeps
            # data-bit edges from being decoded as extra bytes. The next byte
            # may begin immediately after the stop bit(s).
            frames.append({"start_sample": int(start), "value": value,
                           "parity_ok": parity_ok, "stop_ok": True})
            # Floor keeps a following start that lands on the stop boundary.
            # Data edges sit at least a stop bit earlier, so they stay inside.
            next_frame_start = int(np.floor(start + frame_bits * samples_per_bit))
            if len(frames) >= limit:
                break
        else:
            # A failed stop is a resync, not a byte. Skip one bit and keep
            # searching so the attempt does not fill the result limit or hide
            # a later real start.
            next_frame_start = start + bit_width
    return frames


def decode_spi(clk: Waveform, mosi: Waveform, miso: Waveform | None = None,
               cs: Waveform | None = None, *, cpol: int = 0, cpha: int = 0,
               bit_order: str = "msb", bits_per_word: int = 8,
               limit: int = 1000) -> list[dict[str, Any]]:
    """Synchronous SPI words (modes 0..3, MSB/LSB first, optional MISO/CS)."""
    if cpol not in (0, 1) or cpha not in (0, 1):
        raise AnalysisError("cpol/cpha must be 0 or 1")
    if bit_order not in _SPI_BIT_ORDERS:
        raise AnalysisError("bit_order must be msb or lsb")
    if not 1 <= bits_per_word <= 32:
        raise AnalysisError("bits_per_word must be 1..32")
    if not 1 <= limit <= 10000:
        raise AnalysisError("limit must be 1..10000")
    waves = [clk, mosi] + [w for w in (miso, cs) if w is not None]
    _shared_rate(waves)
    n = clk.samples
    if not (mosi.samples == n and all(w.samples == n for w in waves)):
        raise AnalysisError("SPI channels must share a sample count")
    clk_b = _bits(clk)
    mosi_b = _bits(mosi)
    miso_b = _bits(miso) if miso is not None else None
    cs_b = _bits(cs) if cs is not None else None
    rising = np.flatnonzero(~clk_b[:-1] & clk_b[1:]) + 1
    falling = np.flatnonzero(clk_b[:-1] & ~clk_b[1:]) + 1
    # CPHA=0 samples on the first edge (rising for CPOL=0), CPHA=1 on the second.
    sample_rising = cpol == cpha
    edges = rising if sample_rising else falling

    def _pack(seq: np.ndarray) -> int:
        order = seq if bit_order == "msb" else seq[::-1]
        return int(sum(int(bit) << (len(order) - 1 - i) for i, bit in enumerate(order)))

    if cs_b is not None:
        active = ~cs_b  # active low
        regions: list[tuple[int, int]] = []
        i = 0
        while i < n:
            if active[i]:
                j = i
                while j < n and active[j]:
                    j += 1
                regions.append((i, j))
                i = j
            else:
                i += 1
    else:
        regions = [(0, n)]

    words: list[dict[str, Any]] = []
    for region_start, region_end in regions:
        selected = edges[(edges >= region_start) & (edges < region_end)]
        for offset in range(0, len(selected) - bits_per_word + 1, bits_per_word):
            group = selected[offset:offset + bits_per_word]
            word = {"start_sample": int(group[0]), "mosi": _pack(mosi_b[group])}
            if miso_b is not None:
                word["miso"] = _pack(miso_b[group])
            words.append(word)
            if len(words) >= limit:
                return words
    return words


def decode_i2c(scl: Waveform, sda: Waveform, *, limit: int = 1000) -> list[dict[str, Any]]:
    """I2C START/STOP and MSB-first byte + ACK events."""
    if not 1 <= limit <= 10000:
        raise AnalysisError("limit must be 1..10000")
    _shared_rate([scl, sda])
    n = min(scl.samples, sda.samples)
    scl_b = _bits(scl)[:n]
    sda_b = _bits(sda)[:n]
    if n < 2:
        return []
    # START: SDA falls while SCL high. STOP: SDA rises while SCL high.
    start_positions = np.flatnonzero(sda_b[:-1] & ~sda_b[1:] & scl_b[1:]) + 1
    stop_positions = np.flatnonzero(~sda_b[:-1] & sda_b[1:] & scl_b[1:]) + 1
    rising = np.flatnonzero(~scl_b[:-1] & scl_b[1:]) + 1
    boundaries = sorted([(int(p), "start") for p in start_positions]
                        + [(int(p), "stop") for p in stop_positions])
    events: list[dict[str, Any]] = []
    bi = 0
    while bi < len(boundaries) and len(events) < limit:
        pos, kind = boundaries[bi]
        if kind != "start":
            bi += 1
            continue
        j = bi + 1
        while j < len(boundaries) and boundaries[j][1] != "stop":
            j += 1
        stop_pos = boundaries[j][0] if j < len(boundaries) else n
        events.append({"type": "start", "sample": pos})
        segment = rising[(rising > pos) & (rising < stop_pos)]
        for k in range(0, len(segment) - 9 + 1, 9):
            group = segment[k:k + 9]
            data = sda_b[group[:8]]
            value = int(sum(int(bit) << (7 - i) for i, bit in enumerate(data)))
            events.append({"type": "byte", "sample": int(group[0]),
                           "value": value, "ack": not bool(sda_b[group[8]])})
            if len(events) >= limit:
                break
        if j < len(boundaries) and len(events) < limit:
            events.append({"type": "stop", "sample": stop_pos})
        bi = j + 1
    return events
