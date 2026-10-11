"""Bounded offline observation, no valid-sample/crop/completeness interpretation."""
import collections
import hashlib
import itertools
import json
import struct
from pathlib import Path

from protocol_reference import RxParser, convert_to_pc

CAP = 32 * 1024 * 1024


def observe(directory):
    directory = Path(directory)
    raw_path = directory / "raw-rx.bin"
    if not 8 <= raw_path.stat().st_size <= CAP:
        raise ValueError("raw cap")
    raw = raw_path.read_bytes()
    if raw[:8] != b"DL16RX01":
        raise ValueError("magic")
    parser = RxParser()
    channels = [bytearray() for _ in range(16)]
    position = 8
    reads = []
    events = []
    counts = collections.Counter()
    packet_sizes = [collections.Counter() for _ in range(16)]
    while position < len(raw):
        if len(raw) - position < 8:
            raise ValueError("record header")
        length, status = struct.unpack_from("<II", raw, position)
        position += 8
        if length > len(raw) - position or length % 2048:
            raise ValueError("record length/alignment")
        parser.push_bytes(convert_to_pc(raw[position:position + length]))
        position += length
        reads.append((length, status))
        while (message := parser.pop()) is not None:
            counts[message.order] += 1
            if message.order == 1:
                if len(message.payload) < 2 or message.payload[0] >= 16:
                    raise ValueError("channel")
                channel = message.payload[0]
                channels[channel].extend(message.payload[2:])
                packet_sizes[channel][len(message.payload) - 2] += 1
            if message.order in (3, 4, 6):
                events.append({"record": len(reads), "order": message.order,
                               "payload_hex": message.payload.hex()})
    result = {"schema": "task051-stream-observation/v1", "data_integrity": "UNKNOWN",
              "alignment_status": "UNKNOWN", "tail_status": "UNKNOWN",
              "raw_sha256": hashlib.sha256(raw).hexdigest(), "raw_bytes": len(raw),
              "records": len(reads), "read_sizes": dict(collections.Counter(n for n, _ in reads)),
              "status_codes": dict(collections.Counter(s for _, s in reads)),
              "orders": dict(counts), "events": events, "desync_count": parser.desync_count,
              "channels": []}
    for channel, data in enumerate(channels):
        path = directory / f"channel_{channel}.packed"
        if path.stat().st_size > CAP or data != path.read_bytes():
            raise ValueError("stored/replayed payload mismatch")
        # Indices are uncropped storage positions, not a physical common timebase.
        rising = []
        previous = data[0] & 1 if data else 0
        for index in range(1, len(data) * 8):
            bit = (data[index // 8] >> (index % 8)) & 1
            if bit and not previous:
                rising.append(index)
            previous = bit
        result["channels"].append({"channel": channel, "payload_bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(), "packet_sizes": dict(packet_sizes[channel]),
            "first16_hex": data[:16].hex(), "last32_hex": data[-32:].hex(),
            "stored_rising_count": len(rising), "stored_rising_first": rising[:4],
            "stored_rising_last": rising[-4:],
            "stored_rising_deltas": dict(collections.Counter(b-a for a, b in itertools.pairwise(rising))),
            "valid_sample_count": None})
    return result


if __name__ == "__main__":
    import sys
    print(json.dumps(observe(sys.argv[1]), indent=2))
