import json
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from dl16_mcp.session import NativeSession, SessionFailure


WORKER = r'''
import json, os, sys, time
mode = sys.argv[1]
record = sys.argv[2]
for line in sys.stdin:
    try:
        req = json.loads(line)
    except Exception:
        print("not-json", flush=True)
        continue
    with open(record, "a", encoding="utf-8") as f:
        f.write(req.get("command", "") + "\n")
    command = req.get("command")
    if mode == "exit" and command == "status":
        sys.exit(7)
    if mode == "timeout" and command == "capture":
        time.sleep(10)
        continue
    if mode == "malformed" and command == "status":
        print("{bad", flush=True)
        continue
    if mode == "mismatch" and command == "status":
        print(json.dumps({"request_id":"wrong","ok":True}), flush=True)
        continue
    if command == "hello":
        print(json.dumps({"request_id":req["request_id"],"ok":True,"protocol":1}), flush=True)
    elif command == "status":
        print(json.dumps({"request_id":req["request_id"],"ok":True,"session":"ready"}), flush=True)
    elif command == "capture":
        print(json.dumps({"request_id":req["request_id"],"ok":True,"result":{"success":True}}), flush=True)
    elif command == "close":
        print(json.dumps({"request_id":req["request_id"],"ok":True,"session":"closing"}), flush=True)
        sys.exit(0)
'''


def _factory(mode: str, record: Path):
    calls = []

    def popen(_argv, **kwargs):
        calls.append(_argv)
        return subprocess.Popen([sys.executable, "-u", "-c", WORKER, mode, str(record)], **kwargs)

    return popen, calls


def test_session_reuses_one_child_and_correlates_sequential_requests(tmp_path):
    record = tmp_path / "commands.log"
    factory, calls = _factory("ok", record)
    session = NativeSession(Path("worker"), popen_factory=factory)
    try:
        first = session.request({"command": "status"}, timeout_s=2)
        second = session.request({"command": "capture"}, timeout_s=2)
        assert first["session"] == "ready"
        assert second["result"]["success"] is True
        assert first["request_id"] != second["request_id"]
        assert len(calls) == 1
        assert session.pid is not None
        assert record.read_text(encoding="utf-8").splitlines() == ["hello", "status", "capture"]
    finally:
        session.close()
    assert session.pid is None


@pytest.mark.parametrize(
    ("mode", "expected"),
    [("malformed", "SESSION_PROTOCOL_ERROR"), ("mismatch", "SESSION_PROTOCOL_ERROR"), ("exit", "SESSION_EXITED")],
)
def test_session_protocol_failure_invalidates_child(mode, expected, tmp_path):
    factory, _ = _factory(mode, tmp_path / "commands.log")
    session = NativeSession(Path("worker"), popen_factory=factory)
    try:
        with pytest.raises(SessionFailure) as caught:
            session.request({"command": "status"}, timeout_s=2)
        assert caught.value.code == expected
        assert session.pid is None
        with pytest.raises(SessionFailure) as failed:
            session.request({"command": "status"}, timeout_s=2)
        assert failed.value.code == "SESSION_FAILED"
    finally:
        session.close()


def test_session_timeout_terminates_child_and_never_replays_capture(tmp_path):
    record = tmp_path / "commands.log"
    factory, calls = _factory("timeout", record)
    session = NativeSession(Path("worker"), popen_factory=factory)
    with pytest.raises(SessionFailure) as caught:
        session.request({"command": "capture"}, timeout_s=0.15)
    assert caught.value.code == "SESSION_TIMEOUT"
    assert session.pid is None
    assert record.read_text(encoding="utf-8").splitlines() == ["hello", "capture"]
    assert len(calls) == 1
    session.close()


def test_session_close_is_idempotent_and_rejects_later_requests(tmp_path):
    factory, calls = _factory("ok", tmp_path / "commands.log")
    session = NativeSession(Path("worker"), popen_factory=factory)
    assert session.request({"command": "status"}, timeout_s=2)["ok"] is True
    session.close()
    session.close()
    assert len(calls) == 1
    with pytest.raises(SessionFailure) as caught:
        session.request({"command": "status"}, timeout_s=1)
    assert caught.value.code == "SESSION_CLOSED"


def test_concurrent_callers_are_serialized_and_receive_matching_ids(tmp_path):
    record = tmp_path / "commands.log"
    factory, calls = _factory("ok", record)
    session = NativeSession(Path("worker"), popen_factory=factory)
    results = []
    errors = []

    def invoke():
        try:
            results.append(session.request({"command": "status"}, timeout_s=2))
        except Exception as exc:  # pragma: no cover - assertion reports any unexpected failure
            errors.append(exc)

    threads = [threading.Thread(target=invoke) for _ in range(6)]
    try:
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)
        assert not errors
        assert len(results) == 6
        assert len({item["request_id"] for item in results}) == 6
        assert len(calls) == 1
        assert record.read_text(encoding="utf-8").splitlines().count("status") == 6
    finally:
        session.close()
