"""Deterministic subprocess contracts: no executable, device, or wall-clock waits."""
import io
import json
import subprocess
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from dl16_mcp import session as session_module
from dl16_mcp.session import NativeSession, SessionFailure


class ScriptedWorker:
    """Popen-shaped worker delivering a scripted response at stdin.flush()."""

    def __init__(self, owner, *, pid, hello=None, reply=None, resist_terminate=False):
        self.owner = owner
        self.pid = pid
        self.returncode = None
        self.requests = []
        self.actions = []
        self.hello = hello if hello is not None else {"protocol": 1, "commands": ["status", "capture", "pwm", "close"]}
        self.reply = reply
        self.resist_terminate = resist_terminate
        self.stdin = io.StringIO()
        self.stdout = io.StringIO()
        self.stdin.flush = self.respond

    def respond(self):
        request = json.loads(self.stdin.getvalue().splitlines()[-1])
        self.requests.append(request)
        command = request["command"]
        response = {"request_id": request["request_id"], "ok": True}
        if command == "hello":
            response.update(self.hello)
        elif command == "close":
            response["session"] = "closing"
        elif self.reply is not None:
            response = self.reply(request, self)
            if response is None:
                return
        self.owner._stdout_queue.put(("line", json.dumps(response) + "\n"))

    def poll(self):
        return self.returncode

    def terminate(self):
        self.actions.append("terminate")
        if not self.resist_terminate:
            self.returncode = -15

    def kill(self):
        self.actions.append("kill")
        self.returncode = -9

    def wait(self, *, timeout):
        self.actions.append(("wait", timeout))
        if self.returncode is None:
            raise subprocess.TimeoutExpired("scripted-worker", timeout)
        return self.returncode


@pytest.fixture
def owners(monkeypatch):
    monkeypatch.delenv("DL16_SESSION_JOURNAL_DIR", raising=False)
    # Responses are injected synchronously by flush; never launch reader threads.
    monkeypatch.setattr(session_module, "threading", SimpleNamespace(
        RLock=threading.RLock,
        Thread=lambda **kwargs: SimpleNamespace(start=lambda: None),
    ))
    sessions = []
    workers = []

    def make(**options):
        def factory(argv, **kwargs):
            assert argv == ["scripted-worker", "session", "--jsonl"]
            assert kwargs["stderr"] == subprocess.DEVNULL
            worker = ScriptedWorker(owner, pid=700 + len(workers), **options)
            workers.append(worker)
            return worker

        owner = NativeSession(Path("scripted-worker"), popen_factory=factory)
        # All scripted responses are already queued. Absence deterministically
        # simulates expiry rather than waiting on the host scheduler.
        queue_get = owner._stdout_queue.get
        owner._stdout_queue.get = lambda **kwargs: queue_get(block=False)
        sessions.append(owner)
        return owner, workers

    yield make
    for owner in sessions:
        owner.close()


def commands(worker):
    return [request["command"] for request in worker.requests]


@pytest.mark.parametrize("protocol", [None, 0, 2, True, "1"])
def test_incompatible_hello_rejects_before_operation(owners, protocol):
    hello = {"commands": ["capture"]}
    if protocol is not None:
        hello["protocol"] = protocol
    owner, workers = owners(hello=hello)
    with pytest.raises(SessionFailure) as caught:
        owner.request({"command": "capture"}, timeout_s=1)
    assert caught.value.code == "SESSION_PROTOCOL_ERROR"
    assert commands(workers[0]) == ["hello"]
    assert owner.failed and owner.pid is None
    assert workers[0].stdin.closed and workers[0].stdout.closed
    with pytest.raises(SessionFailure, match="explicit restart"):
        owner.request({"command": "status"}, timeout_s=1)
    assert len(workers) == 1


def test_mixed_worker_capabilities_do_not_leak_between_owners(owners):
    old, workers = owners(hello={"protocol": 1, "commands": ["status", "close"]})
    with pytest.raises(SessionFailure) as caught:
        old.request({"command": "pwm", "op": "stop", "output": 0}, timeout_s=1)
    assert caught.value.code == "NATIVE_CAPABILITY_MISSING"
    assert commands(workers[0]) == ["hello"]
    assert not old.failed
    old_pid = old.pid
    assert old.request({"command": "status"}, timeout_s=1)["ok"]

    new, _ = owners()
    assert new.request({"command": "pwm", "op": "stop", "output": 0}, timeout_s=1)["ok"]
    assert commands(workers[1]) == ["hello", "pwm"]
    new.close()
    assert old.pid == old_pid
    assert workers[0].actions == []
    old.close()
    assert commands(workers[0]) == ["hello", "status", "close"]


def test_legacy_hello_without_commands_allows_status_but_not_pwm(owners):
    owner, workers = owners(hello={"protocol": 1})
    assert owner.request({"command": "status"}, timeout_s=1)["ok"]
    with pytest.raises(SessionFailure) as caught:
        owner.request({"command": "pwm"}, timeout_s=1)
    assert caught.value.code == "NATIVE_CAPABILITY_MISSING"
    assert commands(workers[0]) == ["hello", "status"]


def test_timeout_stops_only_failed_owner_and_explicit_fresh_worker_never_replays(owners):
    failed, workers = owners(reply=lambda request, worker: None, resist_terminate=True)
    other, _ = owners()
    assert other.request({"command": "status"}, timeout_s=1)["ok"]
    other_pid = other.pid
    with pytest.raises(SessionFailure) as caught:
        failed.request({"command": "capture", "token": "must-not-replay"}, timeout_s=1)
    assert caught.value.code == "SESSION_TIMEOUT"
    assert commands(workers[1]) == ["hello", "capture"]
    assert workers[1].actions == ["terminate", ("wait", 1.0), "kill", ("wait", 1.0)]
    assert workers[1].stdin.closed and workers[1].stdout.closed
    assert failed.failed and failed.pid is None
    with pytest.raises(SessionFailure) as caught:
        failed.request({"command": "status"}, timeout_s=1)
    assert caught.value.code == "SESSION_FAILED"
    assert len(workers) == 2
    assert other.pid == other_pid and workers[0].actions == []
    failed.close()

    fresh, _ = owners()
    assert fresh.request({"command": "status"}, timeout_s=1)["ok"]
    assert commands(workers[2]) == ["hello", "status"]
    assert all("token" not in request for request in workers[2].requests)
    assert commands(workers[1]) == ["hello", "capture"]


def test_delayed_previous_response_is_fatal_not_accepted_for_new_request(owners):
    def reply(request, worker):
        previous = worker.requests[-2] if len(worker.requests) > 2 else request
        return {"request_id": previous["request_id"], "ok": True}

    owner, workers = owners(reply=reply)
    first = owner.request({"command": "status"}, timeout_s=1)
    with pytest.raises(SessionFailure) as caught:
        owner.request({"command": "capture"}, timeout_s=1)
    assert caught.value.code == "SESSION_PROTOCOL_ERROR"
    assert caught.value.diagnostics["actual_request_id"] == first["request_id"]
    assert caught.value.diagnostics["expected_request_id"] != first["request_id"]
    assert owner.failed and owner.pid is None
    assert commands(workers[0]) == ["hello", "status", "capture"]
    fresh, _ = owners()
    assert fresh.request({"command": "status"}, timeout_s=1)["ok"]
    assert commands(workers[1]) == ["hello", "status"]


def test_broken_write_invalidates_without_replay_or_close_command(owners):
    owner, workers = owners()
    owner.request({"command": "status"}, timeout_s=1)

    def broken_write(_line):
        raise BrokenPipeError("scripted broken pipe")

    workers[0].stdin.write = broken_write
    with pytest.raises(SessionFailure) as caught:
        owner.request({"command": "capture"}, timeout_s=1)
    assert caught.value.code == "SESSION_EXITED"
    assert owner.failed and owner.pid is None
    owner.close()
    assert commands(workers[0]) == ["hello", "status"]
    assert len(workers) == 1


def test_local_oversize_rejection_keeps_owner_usable_without_sending(owners):
    owner, workers = owners()
    with pytest.raises(SessionFailure) as caught:
        owner.request({"command": "capture", "value": "x" * session_module.MAX_LINE_BYTES}, timeout_s=1)
    assert caught.value.code == "SESSION_REQUEST_TOO_LARGE"
    assert commands(workers[0]) == ["hello"]
    assert not owner.failed
    assert owner.request({"command": "status"}, timeout_s=1)["ok"]
    assert commands(workers[0]) == ["hello", "status"]
