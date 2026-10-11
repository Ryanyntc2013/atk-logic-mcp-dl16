"""TASK-051 internal diagnostic gate tests; never open USB."""
import subprocess
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
