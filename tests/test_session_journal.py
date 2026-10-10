import json
import subprocess
import sys
from pathlib import Path

import pytest

from dl16_mcp.journal import SessionJournal
from dl16_mcp.session import NativeSession, SessionFailure

WORKER = r'''
import json,sys,time
for line in sys.stdin:
 r=json.loads(line); c=r['command']
 if c=='hello': out={'ok':True,'protocol':1}
 elif c=='native-error': out={'ok':False,'error_code':'DEVICE_ERROR','message':'complete native failure'}
 elif c=='malformed': print('{broken',flush=True); continue
 elif c=='nonobject': print('[]',flush=True); continue
 elif c=='mismatch': out={'ok':True,'wrong_id':True}
 elif c=='timeout': time.sleep(3); continue
 elif c=='exit': sys.exit(9)
 elif c=='close': out={'ok':True,'session':'closing'}
 else: out={'ok':True,'result':{'success':True,'channels':[2,7]}}
 if c!='mismatch': out['request_id']=r['request_id']
 print(json.dumps(out),flush=True)
'''


def make_session(tmp_path, monkeypatch):
    journal = tmp_path / "journal"
    monkeypatch.setenv("DL16_SESSION_JOURNAL_DIR", str(journal))

    def factory(_argv, **kwargs):
        return subprocess.Popen([sys.executable, "-u", "-c", WORKER], **kwargs)

    return NativeSession(Path(__file__), popen_factory=factory), journal


def read_records(directory):
    paths = list(directory.glob("*.jsonl"))
    assert len(paths) == 1
    return [json.loads(line) for line in paths[0].read_text(encoding="utf-8").splitlines()]


def test_journal_records_full_success_native_error_and_close(tmp_path, monkeypatch):
    session, directory = make_session(tmp_path, monkeypatch)
    assert session.request({"command": "capture", "channels": [2, 7]}, timeout_s=2)["ok"]
    with pytest.raises(SessionFailure) as error:
        session.request({"command": "native-error"}, timeout_s=2)
    assert error.value.code == "DEVICE_ERROR"
    session.close()
    records = read_records(directory)
    requests = [r for r in records if r["type"] == "request"]
    results = [r for r in records if r["type"] == "result"]
    assert [r["request"]["command"] for r in requests] == ["hello", "capture", "native-error", "close"]
    assert all(r["request"]["binary_sha256"] for r in requests)
    assert all(r["schema"] == "dl16-session-journal/v1" and r["timestamp_utc"].endswith("Z") for r in records)
    assert [r["sequence"] for r in records] == list(range(1, len(records) + 1))
    assert all(r["stderr"]["state"] == "unavailable" for r in records)
    assert requests[1]["request"]["configuration_authority"] == "caller_requested"
    assert results[2]["response"]["message"] == "complete native failure"
    assert results[1]["response"]["result"]["channels"] == [2, 7]
    assert any(r["type"] == "cleanup" for r in records)


@pytest.mark.parametrize(("command", "code"), [
    ("malformed", "SESSION_PROTOCOL_ERROR"),
    ("timeout", "SESSION_TIMEOUT"),
    ("exit", "SESSION_EXITED"),
    ("nonobject", "SESSION_PROTOCOL_ERROR"),
    ("mismatch", "SESSION_PROTOCOL_ERROR"),
])
def test_journal_retains_failed_outcomes_without_replay(command, code, tmp_path, monkeypatch):
    session, directory = make_session(tmp_path, monkeypatch)
    with pytest.raises(SessionFailure) as error:
        session.request({"command": command}, timeout_s=0.15)
    assert error.value.code == code
    records = read_records(directory)
    matching = [r for r in records if r.get("type") == "result" and r["outcome"] == code]
    assert len(matching) == 1
    if command == "malformed":
        assert matching[0]["raw_response"].startswith("{broken")
    elif command == "nonobject":
        assert matching[0]["raw_response"].startswith("[]")
    elif command == "mismatch":
        assert matching[0]["response"]["wrong_id"] is True
        assert matching[0]["response_request_id"] is None
    session.close()
    assert sum(r.get("type") == "request" and r["request"]["command"] == command for r in read_records(directory)) == 1


def test_journal_failure_prevents_command_send(tmp_path, monkeypatch):
    journal = tmp_path / "journal"
    monkeypatch.setenv("DL16_SESSION_JOURNAL_DIR", str(journal))
    blocker = tmp_path / "a-file"
    blocker.write_text("not a directory")
    journal.mkdir()
    (journal / "dl16-session-fixed.jsonl").write_text("", encoding="utf-8")
    session, _ = make_session(tmp_path, monkeypatch)
    bad_journal = tmp_path / "bad-journal"
    bad_journal.write_text("blocked", encoding="utf-8")
    session._journal = SessionJournal(bad_journal)
    with pytest.raises(SessionFailure) as error:
        session.request({"command": "capture"}, timeout_s=1)
    assert error.value.code == "SESSION_JOURNAL_ERROR"
    assert session.failed


def test_journal_disabled_by_default(tmp_path, monkeypatch):
    monkeypatch.delenv("DL16_SESSION_JOURNAL_DIR", raising=False)
    session, _ = make_session(tmp_path, monkeypatch)
    session._journal = None
    session.request({"command": "status"}, timeout_s=2)
    session.close()
    assert not list(tmp_path.glob("*.jsonl"))


def test_invalid_response_bytes_are_journaled(tmp_path, monkeypatch):
    session, directory = make_session(tmp_path, monkeypatch)
    with pytest.raises(SessionFailure):
        session.request({"command": "malformed"}, timeout_s=2)
    result = [r for r in read_records(directory) if r.get("type") == "result" and r.get("outcome") == "SESSION_PROTOCOL_ERROR"]
    assert result[0]["raw_response"] == "{broken\n"
    session.close()


def test_logging_disabled_does_not_read_binary(tmp_path, monkeypatch):
    monkeypatch.delenv("DL16_SESSION_JOURNAL_DIR", raising=False)
    executable = tmp_path / "fake-binary"
    executable.write_bytes(b"stub")
    session = NativeSession(executable, popen_factory=lambda _argv, **kwargs:
                              subprocess.Popen([sys.executable, "-u", "-c", WORKER], **kwargs))
    session.request({"command": "status"}, timeout_s=2)
    assert session._binary_sha256 is None
    session.close()


def test_unique_journals_never_overwrite(tmp_path):
    first = SessionJournal(tmp_path)
    second = SessionJournal(tmp_path)
    first.record({"value": 1})
    second.record({"value": 2})
    first.close()
    second.close()
    paths = list(tmp_path.glob("*.jsonl"))
    assert len(paths) == 2
    assert {json.loads(path.read_text(encoding="utf-8"))["value"] for path in paths} == {1, 2}


def test_cleanup_timeout_is_not_reported_as_closed(monkeypatch, tmp_path):
    session, directory = make_session(tmp_path, monkeypatch)
    session.request({"command": "status"}, timeout_s=2)
    proc = session._proc
    assert proc is not None
    original_wait = proc.wait

    def wait_with_failure(*, timeout=None):
        raise subprocess.TimeoutExpired("worker", timeout)

    proc.wait = wait_with_failure
    proc.kill = lambda: None
    session.close()
    proc.wait = original_wait
    cleanup = [r for r in read_records(directory) if r.get("type") == "cleanup"][-1]
    assert cleanup["outcome"] == "failed"
    assert cleanup["kill_error"]
    assert cleanup["returncode"] is None


def test_close_journal_error_propagates_after_cleanup(tmp_path, monkeypatch):
    session, _ = make_session(tmp_path, monkeypatch)
    session.request({"command": "status"}, timeout_s=2)

    class BrokenCloseJournal:
        def record(self, _entry):
            raise OSError("disk full")

        def close(self):
            pass

    session._journal = BrokenCloseJournal()
    with pytest.raises(SessionFailure) as caught:
        session.close()
    assert caught.value.code == "SESSION_JOURNAL_ERROR"
    assert session._proc is None


def test_journal_supports_escaped_bounded_response(tmp_path):
    journal = SessionJournal(tmp_path)
    response = {"value": "\x00" * 10000}
    raw = json.dumps(response)
    assert len(raw.encode("utf-8")) < 65536
    journal.record({"response": response, "raw_response": raw})
    journal.close()
    records = read_records(tmp_path)
    assert records[0]["response"] == response
    assert records[0]["raw_response"] == raw
