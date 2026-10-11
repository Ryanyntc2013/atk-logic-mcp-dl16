"""TASK-050 actual USB-free native storage foundation, NOT live Stream."""
import json
import subprocess
import time
from pathlib import Path

import pytest
from test_session import _factory

from dl16_mcp import backend, service
from dl16_mcp.session import NativeSession, SessionFailure

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tests/native/build/Release/dl16-incremental-writer-test.exe"
NATIVE = ROOT / "external/ATK-Logic-Mcp/build/Release/atk-dl16.exe"
VECTORS = json.loads((ROOT / "tests/vectors/task050-tail-preservation-v1.json").read_text())


def run_writer(mode, directory):
    return subprocess.run([str(HARNESS), mode, str(directory)], check=False, capture_output=True, text=True, timeout=5)


@pytest.mark.skipif(not HARNESS.exists(), reason="actual native writer harness not built")
@pytest.mark.parametrize("vector", VECTORS["vectors"])
def test_native_versioned_tail_preservation(tmp_path, vector):
    directory = tmp_path / "tail"
    assert run_writer(vector["mode"], directory).returncode == 0
    meta = json.loads((directory / "stream_meta.json").read_text())
    assert meta["tail_policy"] == VECTORS["policy"]
    assert meta["data_integrity"] == "INCOMPLETE"
    assert meta["tail_status"] == "UNKNOWN"
    assert meta["requested_samples"] == vector["requested_samples"]
    assert meta["channels"][0]["valid_sample_count"] is None
    assert meta["channels"][0]["original_packed_start_sample_index"] == 0
    assert meta["channels"][0]["original_packed_end_sample_index"] == vector["stored_bytes"] * 8
    assert (directory / "ch8.packed.bin").read_bytes() == b"\x81" * vector["stored_bytes"]
    assert not list(directory.glob("*edges*"))


@pytest.mark.skipif(not HARNESS.exists(), reason="actual native writer harness not built")
def test_actual_writer_caps_overwrite_errors_and_abandonment(tmp_path):
    folder = tmp_path / "write"
    assert run_writer("write", folder).returncode == 0
    expected = b"\x55\xaa\x81"
    assert (folder / "ch8.packed.bin").read_bytes() == expected
    assert run_writer("write", folder).returncode == 3
    assert (folder / "ch8.packed.bin").read_bytes() == expected
    cap = tmp_path / "cap"
    assert run_writer("cap", cap).returncode == 3
    meta = json.loads((cap / "stream_meta.json").read_text())
    assert meta["total_bytes"] == 3
    assert meta["reason"] == "BYTE_CAP"
    assert meta["status"] == "INCOMPLETE"
    assert (cap / "ch14.packed.bin").stat().st_size == 0
    abandon = tmp_path / "abandon"
    assert run_writer("abandon", abandon).returncode == 0
    assert json.loads((abandon / "stream_meta.json").read_text())["reason"] == "ABANDONED"
    assert run_writer("meta-error", tmp_path / "failed").returncode == 3
    invalid = tmp_path / "invalid"
    assert run_writer("invalid", invalid).returncode == 0
    assert not invalid.exists()
    assert run_writer("chunk", tmp_path / "chunk").returncode == 0


@pytest.mark.skipif(not HARNESS.exists(), reason="actual native writer harness not built")
def test_actual_incremental_owner_cancel_and_eof(tmp_path):
    directory = tmp_path / "control"
    process = subprocess.Popen([str(HARNESS), "control", str(directory)], stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, text=True)

    def request(command, **fields):
        process.stdin.write(json.dumps({"request_id": command, "command": command, **fields}) + "\n")
        process.stdin.flush()
        return json.loads(process.stdout.readline())

    try:
        assert request("capture_start", channels=[8, 14], sample_rate_hz=1000000,
                       duration_ms=30000)["state"] == "running"
        deadline = time.monotonic() + 2
        while not (directory / "ch8.packed.bin").exists() or (directory / "ch8.packed.bin").stat().st_size == 0:
            assert time.monotonic() < deadline
            time.sleep(0.005)
        # Bytes are already visible while the operation is running, not a final RAM save.
        assert request("capture_poll", operation_id="capture_start")["state"] == "running"
        assert request("capture_cancel", operation_id="capture_start")["ok"]
        while True:
            reply = request("capture_poll", operation_id="capture_start")
            if reply["state"] == "finished":
                break
            assert time.monotonic() < deadline
        assert reply["response"]["result"]["data_integrity"] == "INCOMPLETE"
        assert json.loads((directory / "stream_meta.json").read_text())["reason"] == "CANCELLED"
        assert request("close")["ok"]
        assert process.wait(timeout=2) == 0
    finally:
        if process.poll() is None:
            process.stdin.close()
            process.wait(timeout=5)
        process.stdout.close()
        if not process.stdin.closed:
            process.stdin.close()
    eof_directory = tmp_path / "eof"
    request_line = json.dumps({"request_id": "eof", "command": "capture_start", "channels": [8],
                               "sample_rate_hz": 1000000, "duration_ms": 30000})
    reply = subprocess.run([str(HARNESS), "control", str(eof_directory)], check=False, input=request_line + "\n",
                           capture_output=True, text=True, timeout=2)
    assert reply.returncode == 0
    assert json.loads((eof_directory / "stream_meta.json").read_text())["reason"] == "CANCELLED"


@pytest.mark.parametrize("command", ["stream_start", "stream_poll", "stream_cancel"])
def test_legacy_workers_reject_before_stream_dispatch(tmp_path, command):
    record = tmp_path / "commands"
    factory, _ = _factory("ok", record)
    session = NativeSession(Path("old-worker"), popen_factory=factory)
    try:
        with pytest.raises(SessionFailure) as exc:
            session.request({"command": command}, timeout_s=2)
        assert exc.value.code == "STREAM_TAIL_UNVERIFIED"
        assert record.read_text().splitlines() == ["hello"]
    finally:
        session.close()


@pytest.mark.skipif(not NATIVE.exists(), reason="patched native worker not built")
def test_actual_worker_never_advertises_stream_or_opens_for_stream():
    requests = [json.dumps({"request_id": "hello", "command": "hello", "protocol": 1}),
                json.dumps({"request_id": "stream", "command": "stream_start"}),
                json.dumps({"request_id": "close", "command": "close"})]
    reply = subprocess.run([str(NATIVE), "session", "--jsonl"], input="\n".join(requests) + "\n",
                           capture_output=True, text=True, timeout=3, check=True)
    results = {result["request_id"]: result for result in map(json.loads, reply.stdout.splitlines())}
    assert not any("stream" in capability.lower() for capability in results["hello"]["commands"])
    assert results["stream"]["error_code"] == "STREAM_TAIL_UNVERIFIED"
    assert results["close"]["ok"]


def test_mcp_service_boundary_never_launches_or_creates_artifacts(monkeypatch):
    monkeypatch.setattr(backend, "find_native_cli", lambda: pytest.fail("must not launch"))
    monkeypatch.setattr(backend, "captures_dir", lambda: pytest.fail("must not create"))
    assert service.logic_stream_start()["error_code"] == "EXPERIMENTAL_OPT_IN_REQUIRED"
    assert service.logic_stream_start(True)["error_code"] == "STREAM_TAIL_UNVERIFIED"
    from dl16_mcp import server
    assert server.logic_stream_start(True)["stream_available"] is False
