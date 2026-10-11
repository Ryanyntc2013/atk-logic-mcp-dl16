"""Reject premature units/crop conclusions using immutable TASK051 observations."""
import json
from pathlib import Path

import pytest
from task052_hypotheses import compare, predictions
from test_task051_observation import ARCHIVE, VECTOR
from task051_observation import observe

PROFILE = json.loads((Path(__file__).parent / "vectors/task052-hypotheses-v1.json").read_text())


def test_versioned_discriminating_predictions():
    for case in PROFILE["cases"]:
        assert predictions(case["requested_samples"]) == {k: v for k, v in case.items() if k not in ("depth_ms", "requested_samples")}
    assert PROFILE["selected_crop"] is None
    assert PROFILE["archive_raw_sha256"] == VECTOR["raw_sha256"]


def test_order3_units_remain_mode_specific_hypotheses():
    event = next(e for e in VECTOR["events"] if e["order"] == 3)
    result = compare(event["payload_hex"], 400000, 50016)
    assert result["offset_raw"] == 22
    assert result["count_fields_raw"] == [25001] * 16
    assert result["buffer_source_byte_unit_bits"] == [200008] * 16
    assert result["candidate_word_unit_bits"] == [400016] * 16
    assert all(result["matches_observed_lengths"].values())
    assert result["selected_crop"] is result["valid_samples"] is None
    assert result["tail_status"] == "UNKNOWN"
    with pytest.raises(ValueError):
        compare(event["payload_hex"][:-2], 400000, 50016)


@pytest.mark.skipif(not ARCHIVE.exists(), reason="immutable physical archive not present")
def test_archive_hash_and_exact_terminal_runs_without_trimming():
    result = observe(ARCHIVE)
    assert result["raw_sha256"] == PROFILE["archive_raw_sha256"]
    assert len(result["channels"]) == 16
    for channel in range(16):
        data = (ARCHIVE / f"channel_{channel}.packed").read_bytes()
        assert len(data) == 50016
        assert data[-16:] == b"\xaa" * 16
        assert data[-17] != 0xaa
