"""TASK-051 internal diagnostic gate tests; never open USB."""
import json
import subprocess

from protocol_reference import compute_crc32, convert_to_device, convert_to_pc
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXE = ROOT / "tests" / "native" / "build" / "Release" / "dl16-stream-evidence.exe"
pytestmark = pytest.mark.skipif(not EXE.exists(), reason="native evidence harness not built")


def run(*args):
    return subprocess.run([str(EXE), *args], check=False, capture_output=True, text=True, timeout=5)


def test_native_stream_bounds_and_exact_frames():
    result = run("--self-test")
    assert result.returncode == 0, result.stderr
    assert "SYNTHETIC_OFFLINE" in result.stdout
    assert "PWM configure/stop exact production helper contract passed" in result.stdout


def test_native_tx_evidence_roundtrip_exact_payloads_and_cached_profile():
    result = run("--self-test")
    assert result.returncode == 0, result.stderr
    rows = [json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")]
    assert [row["kind"] for row in rows] == ["parameter", "trigger", "device_profile"]
    expected = [bytes.fromhex("001006801a0600000000000000"), bytes.fromhex("00000000f00000f001")]
    for row, payload in zip(rows, expected):
        wire, linear = bytes.fromhex(row["transport_hex"]), bytes.fromhex(row["linear_hex"])
        assert len(wire) == len(linear) == 2048
        assert convert_to_pc(wire) == linear
        assert convert_to_device(linear) == wire
        assert linear[11:11+len(payload)] == payload
        footer = 10 + linear[10]
        assert linear[footer] == 11
        assert int.from_bytes(linear[footer+1:footer+5], "little") == compute_crc32(linear[9:footer])
        assert row["authority"] == "HOST_CONSTRUCTED_NOT_BUS_OBSERVED"
    profile = rows[-1]
    assert bytes.fromhex(profile["model_name_hex"]) == b'synthetic"fixture'
    assert profile["zero_or_unknown_fields_are_not_verified"] is True
    assert "CACHED" in profile["authority"]


@pytest.mark.parametrize("rate,duration,cap", [
    ("20000001", "20", "33554432"),
    ("25000000", "20", "33554432"),
    ("20000000", "101", "33554432"),
    ("20000000", "0", "33554432"),
    ("20000000", "20", "33554433"),
    ("20000000", "20", "15"),
    ("-1", "20", "33554432"),
    ("20000000garbage", "20", "33554432"),
])
def test_invalid_limits_before_device_or_filesystem(rate, duration, cap):
    destination = ROOT / "artifacts" / "task051-invalid-must-not-exist"
    assert not destination.exists()
    result = run("--diagnostic-stream-opt-in", str(destination), rate, duration, cap)
    assert result.returncode == 2
    assert not destination.exists()


def test_opt_in_mandatory_even_for_valid_bounds():
    result = run("--stream", str(ROOT / "artifacts" / "task051-no-opt-in"), "20000000", "20", "33554432")
    assert result.returncode == 2
    assert "usage:" in result.stderr
