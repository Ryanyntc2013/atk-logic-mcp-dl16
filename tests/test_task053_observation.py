"""Observed depth vectors disprove candidate rules, not establish crop validity."""
import json
from pathlib import Path

import pytest
from task053_observation import profile

ROOT = Path(__file__).resolve().parents[1]


def vector(depth):
    return json.loads((ROOT / f"tests/vectors/task053-depth{depth}-observation-v1.json").read_text())


@pytest.mark.parametrize("depth,size,count,offset", [(10, 25008, (1 << 40)-16, 17), (30, 75008, (1 << 40)-8, 21)])
def test_observed_fields_fail_closed(depth, size, count, offset):
    v = vector(depth)
    assert v["data_integrity"] == v["tail_status"] == v["alignment_status"] == "UNKNOWN"
    assert v["order3_channel_count_fields"] == [count] * 16
    assert v["order3_trigger_offset"] == offset
    assert v["orders"]["6"] == 2
    assert v["device_profile"]["mcu_firmware_version"] == 19
    assert v["device_profile"]["fpga_firmware_version"] == 222
    parameter, trigger = v["tx"]
    p = bytes.fromhex(parameter["payload_hex"])
    assert p[:3] == bytes([0, 16, 6])
    assert int.from_bytes(p[3:8], "little") == v["requested_samples"]
    assert p[8:] == bytes(5)
    assert trigger["payload_hex"] == "00000000f00000f001"
    for channel in v["channels"]:
        assert channel["payload_bytes"] == size
        assert channel["observed_aa_suffix_bytes"] == 8
        assert channel["excess_over_requested_bytes"] == 8
        assert not channel["count_times_two_plus_six_matches"]
        assert channel["valid_sample_count"] is None


def test_cross_depth_hypotheses_not_universal():
    ten, thirty = vector(10), vector(30)
    twenty = json.loads((ROOT / "tests/vectors/task051-stream-observation-v1.json").read_text())
    assert 2 * 25001 + 6 == 50008
    assert all(c["payload_bytes"] != 2 * 25001 + 6 for c in twenty["channels"])
    assert ten["channels"][0]["payload_bytes"] != 25000 + 16
    assert ten["channels"][0]["payload_bytes"] != ((25000 + 31) // 32) * 32
    assert thirty["channels"][0]["payload_bytes"] != 75000 + 16
    assert thirty["channels"][0]["payload_bytes"] == ((75000 + 31) // 32) * 32
    assert twenty["channels"][0]["payload_bytes"] != 50000 + 8


@pytest.mark.parametrize("depth", [10, 30])
def test_archive_exact_reconstruction_and_tx_crc(depth):
    archive = ROOT / f"artifacts/hil/DL16-TASK-053/depth-{depth}"
    if not archive.exists():
        pytest.skip("parent archive absent; never synthesize replacement HIL")
    assert json.loads(json.dumps(profile(archive))) == vector(depth)
