"""Executable versioned alternatives, NOT a crop function or runtime contract."""


def predictions(requested_samples):
    if requested_samples <= 0 or requested_samples % 16:
        raise ValueError("hypothesis domain: positive whole 16-sample words")
    packed = requested_samples // 8
    return {
        "fixed16-v1": packed + 16,
        "align32-v1": (packed + 31) // 32 * 32,
        "word-count-plus14-v1": 2 * (packed // 2 + 1) + 14,
        "candidate_order3_words-v1": packed // 2 + 1,
    }


def compare(order3_payload_hex, requested_samples, payload_bytes):
    raw = bytes.fromhex(order3_payload_hex)
    if len(raw) != 88:
        raise ValueError("requires TASK051 2+5+16*5+1 layout")
    offset = int.from_bytes(raw[2:7], "little")
    fields = [int.from_bytes(raw[7+i*5:12+i*5], "little") for i in range(16)]
    alternatives = predictions(requested_samples)
    return {"schema": "task052-order3-hypotheses/v1", "alignment_status": "UNKNOWN",
            "tail_status": "UNKNOWN", "valid_samples": None, "offset_raw": offset,
            "count_fields_raw": fields, "buffer_source_byte_unit_bits": [n*8 for n in fields],
            "candidate_word_unit_bits": [n*16 for n in fields],
            "matches_observed_lengths": {name: value == payload_bytes for name, value in alternatives.items()
                                         if name != "candidate_order3_words-v1"},
            "predictions": alternatives, "selected_crop": None}
