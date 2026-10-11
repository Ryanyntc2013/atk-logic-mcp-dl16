import json
from pathlib import Path

import pytest

from dl16_mcp.order3_diagnostics import diagnose_order3

ROOT = Path(__file__).resolve().parent


def _vector_payload(depth):
    vector = json.loads((ROOT / f"vectors/task053-depth{depth}-observation-v1.json").read_text())
    return bytes.fromhex(next(event["payload_hex"] for event in vector["events"] if event["order"] == 3))


@pytest.mark.parametrize("depth,expected", [(10, (1 << 40) - 16), (30, (1 << 40) - 8)])
def test_task053_stream_variants_preserve_raw_and_fail_closed(depth, expected):
    payload = _vector_payload(depth)
    result = diagnose_order3(payload, mode="STREAM", profile=f"task053-depth{depth}-v1", request_depth_samples=depth * 20000)
    assert result["raw_hex"] == payload.hex()
    assert result["count_fields_raw_u40"] == [expected] * 16
    assert result["count_fields_signed40_hypothesis_not_interpretation"] == [-16 if depth == 10 else -8] * 16
    assert result["count_fields_within_crop_budget_bytes_or_none"] == [None] * 16
    assert result["mode_status"] == "UNKNOWN_STREAM_UNITS; preserve_raw_no_crop"
    assert result["selected_crop"] is result["valid_sample_count"] is None
    assert result["alignment_status"] == result["tail_status"] == "UNKNOWN"


def test_task051_buffer_convention_is_scoped_and_does_not_change():
    vector = json.loads((ROOT / "vectors/task051-stream-observation-v1.json").read_text())
    raw = bytes.fromhex(next(e["payload_hex"] for e in vector["events"] if e["order"] == 3))
    result = diagnose_order3(raw, mode="BUFFER", profile="task051-observed-layout-v1", request_depth_samples=400000)
    assert result["count_fields_raw_u40"] == [25001] * 16
    assert result["count_fields_within_crop_budget_bytes_or_none"] == [25001] * 16
    assert "BUFFER_BYTE_COUNT_SOURCE_CONVENTION" in result["mode_status"]
    assert result["selected_crop"] is None


def test_synthetic_malformed_extreme_and_bounded_result():
    raw = bytearray(88)
    raw[7:12] = ((1 << 40) - 1).to_bytes(5, "little")
    raw[-1] = 0xA5
    result = diagnose_order3(raw, mode="STREAM", profile="synthetic-extreme-v1", request_depth_samples=1)
    assert len(result["raw_hex"]) == 176
    assert result["count_fields_raw_u40"][0] == (1 << 40) - 1
    assert result["count_fields_signed40_hypothesis_not_interpretation"][0] == -1
    assert result["count_fields_within_crop_budget_bytes_or_none"][0] is None
    for malformed in (b"", bytes(87), bytes(89)):
        with pytest.raises(ValueError):
            diagnose_order3(malformed, mode="STREAM", profile="test", request_depth_samples=1)
    for depth in (-1, True):
        with pytest.raises(ValueError):
            diagnose_order3(raw, mode="STREAM", profile="test", request_depth_samples=depth)
    with pytest.raises(ValueError):
        diagnose_order3(raw, mode="STREAM", profile="test", request_depth_samples=1, max_crop_bytes=1 << 40)
