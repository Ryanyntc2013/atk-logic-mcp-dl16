import json
import os
import subprocess
from pathlib import Path

import pytest

from dl16_mcp import backend
from dl16_mcp.config import CaptureRequest


@pytest.fixture
def replay_cli():
    root = Path(__file__).resolve().parents[1]
    name = "dl16-raw-rx-replay.exe" if os.name == "nt" else "dl16-raw-rx-replay"
    build = root / "tests" / "native" / "build"
    for executable in (build / "Release" / name, build / name):
        if executable.is_file():
            return executable
    pytest.skip("dl16-raw-rx-replay executable not built in tests/native/build")


def replay(executable, *args):
    return subprocess.run([str(executable), *map(str, args)],
                          capture_output=True, text=True, timeout=10)


def raw_banks(pc_data):
    import protocol_reference as ref
    padding = (-len(pc_data)) % 2048
    return ref.convert_to_device(pc_data + bytes(padding))


@pytest.mark.parametrize("frag", [1, 5, 17, 2048, 65536, 0])
def test_offline_raw_replay_helper_parses_arbitrary_fragments(tmp_path, replay_cli, frag):
    import protocol_reference as ref
    f4 = ref.build_rx_frame(4, bytes([0, 0, ref.CMD_SIMPLE_TRIGGER, 3]))
    f6 = ref.build_rx_frame(6, b"")
    # Channel packet crosses multiple raw banks; messages span feed fragments.
    f1 = ref.build_rx_frame(1, bytes([3, 0]) + bytes(4096))
    raw_file = tmp_path / "stream.bin"
    raw_file.write_bytes(raw_banks(f4 + f1 + f6))
    res = replay(replay_cli, "--raw", raw_file, "--frag-size", frag, "--json")
    assert res.returncode == 0, res.stderr
    data = json.loads(res.stdout)
    assert data["total_raw_bytes"] == 6144
    assert data["aligned_bytes"] == 6144
    assert data["unaligned_tail_bytes"] == 0
    assert data["total_messages"] == 3
    assert data["trigger_ack_received"] is True
    assert data["capture_complete_received"] is True
    assert data["first_orders"] == [4, 1, 6]
    assert data["evidence_source"] == "OFFLINE_REPLAY"
    assert data["input_provenance"] == "UNKNOWN"
    assert data["data_integrity"] == "UNKNOWN"
    assert data["capture_completeness"] == "UNKNOWN"


@pytest.mark.parametrize("args", [
    [], ["--unknown"], ["--raw"], ["--frag-size"],
    ["--frag-size", "-1"], ["--frag-size", "+1"],
    ["--frag-size", "2junk"], ["--frag-size", "65537"],
    ["--frag-size", "99999999999999999999999999"],
    ["--json", "--json"], ["--frag-size", "1", "--frag-size", "2"],
    ["--raw", "a", "--raw", "b"], ["--help", "--unknown"],
])
def test_offline_raw_replay_rejects_malformed_cli(replay_cli, args):
    res = replay(replay_cli, *args)
    assert res.returncode != 0
    assert "Error:" in res.stderr
    assert not res.stdout


@pytest.mark.parametrize("size", [0, 2049, 33556480])
def test_offline_raw_replay_rejects_invalid_file_sizes(tmp_path, replay_cli, size):
    raw_file = tmp_path / "invalid.bin"
    with raw_file.open("wb") as output:
        output.truncate(size)
    res = replay(replay_cli, "--raw", raw_file, "--json")
    assert res.returncode != 0
    assert "Error:" in res.stderr
    assert not res.stdout


def test_offline_raw_replay_bounds_message_summary(tmp_path, replay_cli):
    import protocol_reference as ref
    raw_file = tmp_path / "many.bin"
    raw_file.write_bytes(raw_banks(ref.build_rx_frame(6, b"") * 1000))
    res = replay(replay_cli, "--raw", raw_file, "--json")
    assert res.returncode == 0, res.stderr
    data = json.loads(res.stdout)
    assert data["total_messages"] == 1000
    assert len(data["first_orders"]) == 32
    assert data["capture_completeness"] == "UNKNOWN"
    assert len(res.stdout) < 2048


def test_offline_raw_replay_accepts_bounded_file_limit(tmp_path, replay_cli):
    raw_file = tmp_path / "limit.bin"
    with raw_file.open("wb") as output:
        output.truncate(33554432)
    res = replay(replay_cli, "--raw", raw_file, "--json")
    assert res.returncode == 0, res.stderr
    data = json.loads(res.stdout)
    assert data["total_raw_bytes"] == 33554432
    assert data["total_messages"] == 0
    assert data["capture_completeness"] == "UNKNOWN"
    assert data["buffered_bytes"] == 0


def test_offline_raw_replay_complete_marker_does_not_prove_complete_data(tmp_path, replay_cli):
    import protocol_reference as ref
    raw_file = tmp_path / "incomplete.bin"
    # An incomplete maximum-length frame remains pending after a Complete marker.
    pc_data = ref.build_rx_frame(6, b"") + b"\x0a\x01\xff\xff"
    raw_file.write_bytes(raw_banks(pc_data))
    res = replay(replay_cli, "--raw", raw_file, "--json")
    assert res.returncode == 0, res.stderr
    data = json.loads(res.stdout)
    assert data["capture_complete_received"] is True
    assert data["buffered_bytes"] == 2042
    assert data["capture_completeness"] == "UNKNOWN"
    assert data["data_integrity"] == "UNKNOWN"


def test_raw_rx_logging_diagnostics_exposure_on_failure(monkeypatch, tmp_path):
    """Contract mock only: native raw-RX log production is not exercised."""
    file = tmp_path / "atk-dl16.exe"
    file.write_text("mock")
    monkeypatch.setenv("DL16_CLI_PATH", str(file))

    # Test error returned when native capture outputs write error
    err_json = json.dumps({
        "success": False,
        "error_code": "ARTIFACT_WRITE_ERROR",
        "message": "Failed to write raw RX log: disk full",
        "raw_rx_log": {
            "enabled": True,
            "error": "Failed to write raw RX log: disk full",
            "bytes_written": 1024,
            "reads_logged": 1
        }
    })

    class R:
        returncode = 1
        stdout = err_json
        stderr = ""

    from unittest.mock import patch
    with patch("dl16_mcp.backend.subprocess.run", return_value=R()):
        res = backend.capture(CaptureRequest())
    assert res["success"] is False
    assert res["error_code"] == "ARTIFACT_WRITE_ERROR"
    assert res.get("raw_rx_log", {}).get("error") == "Failed to write raw RX log: disk full"


def test_raw_rx_logging_truncation_status(monkeypatch, tmp_path):
    """Contract mock only: pass-through of claimed native logging metadata."""
    file = tmp_path / "atk-dl16.exe"
    file.write_text("mock")
    monkeypatch.setenv("DL16_CLI_PATH", str(file))

    # Truncated capture at 32MiB completes capture successfully without failing
    trunc_json = json.dumps({
        "success": True,
        "data_integrity": "COMPLETE",
        "capture_complete_received": True,
        "trigger_ack_received": True,
        "raw_rx_log": {
            "enabled": True,
            "truncated": True,
            "max_bytes": 33554432,
            "bytes_written": 33554432,
            "reads_logged": 16384,
            "sha256": "abcdef123456"
        }
    })

    class R:
        returncode = 0
        stdout = trunc_json
        stderr = ""

    from unittest.mock import patch
    with patch("dl16_mcp.backend.subprocess.run", return_value=R()):
        res = backend.capture(CaptureRequest())
    assert res["success"] is True
    assert res.get("raw_rx_log", {}).get("truncated") is True


def test_offline_raw_replay_rejects_unaligned_tail(tmp_path, replay_cli):
    import protocol_reference as ref
    complete = ref.build_rx_frame(6, b"")
    raw_file = tmp_path / "tail.bin"
    # Even a plausible decoded frame in the unknown raw tail must not be fed.
    raw_file.write_bytes(raw_banks(complete) + complete)
    res = replay(replay_cli, "--raw", raw_file, "--json")
    assert res.returncode != 0
    assert "unaligned raw tail" in res.stderr
    assert not res.stdout
