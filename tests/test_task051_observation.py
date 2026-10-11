"""Versioned observation is a capture profile, never a universal Stream contract."""
import json
from pathlib import Path

import pytest
from task051_observation import observe

ROOT = Path(__file__).resolve().parents[1]
VECTOR = json.loads((ROOT / "tests/vectors/task051-stream-observation-v1.json").read_text())
ARCHIVE = ROOT / "artifacts/hil/DL16-TASK-051/stream-02"


def test_versioned_profile_never_promotes_completeness():
    assert VECTOR["data_integrity"] == VECTOR["tail_status"] == VECTOR["alignment_status"] == "UNKNOWN"
    assert VECTOR["records"] == 74
    assert VECTOR["raw_bytes"] == 1213016
    assert VECTOR["read_sizes"] == {"16384": 74}
    assert VECTOR["orders"] == {"1": 400, "2": 187, "3": 1, "4": 1, "6": 3}
    assert VECTOR["order3_channel_count_fields"] == [25001] * 16
    for channel in VECTOR["channels"]:
        assert channel["payload_bytes"] == 50016
        assert channel["packet_sizes"] == {"2032": 24, "1248": 1}
        assert channel["last32_hex"].endswith("aa" * 16)
        assert channel["valid_sample_count"] is None
    assert 25001 * 8 < VECTOR["requested_samples"] < 50016 * 8
    assert [event["record"] for event in VECTOR["events"] if event["order"] == 6] == [74] * 3


@pytest.mark.skipif(not ARCHIVE.exists(), reason="parent physical archive unavailable; profile-only tests remain offline")
def test_parent_raw_reconstructs_exact_stored_bytes_without_modification():
    observation = json.loads(json.dumps(observe(ARCHIVE)))
    for key, value in observation.items():
        assert value == VECTOR[key], key
