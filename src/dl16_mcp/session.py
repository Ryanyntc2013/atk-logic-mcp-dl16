"""Owner for one persistent native JSONL worker process.

The manager serializes every request, correlates request IDs, and never replays a
request after an ambiguous worker/protocol failure. It owns only the child it starts.
"""
from __future__ import annotations

import atexit
import hashlib
import json
import os
from pathlib import Path
import queue
import subprocess
import threading
import time
from typing import Any, Callable

from .journal import SessionJournal

MAX_LINE_BYTES = 64 * 1024
STOP_GRACE_SECONDS = 1.0


class SessionFailure(RuntimeError):
    def __init__(self, code: str, message: str, *, diagnostics: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.diagnostics = diagnostics or {}


class NativeSession:
    def __init__(self, executable: Path, *, popen_factory=None,
                 observer: Callable[[dict[str, Any]], None] | None = None):
        self.executable = Path(executable)
        self._popen_factory = popen_factory or subprocess.Popen
        self._proc: subprocess.Popen[str] | None = None
        self._stdout_queue: queue.Queue[tuple[str, Any]] = queue.Queue()
        self._lock = threading.RLock()
        self._counter = 0
        self._failed = False
        self._closed = False
        self._hello = False
        self.capabilities: set[str] = set()
        self._observer = observer
        journal_dir = os.environ.get("DL16_SESSION_JOURNAL_DIR")
        self._journal = SessionJournal(Path(journal_dir).expanduser()) if journal_dir else None
        self._binary_sha256: str | None = None
        self._journal_sequence = 0
        self.last_diagnostics: dict[str, Any] = {}

    @property
    def pid(self) -> int | None:
        proc = self._proc
        return proc.pid if proc is not None and proc.poll() is None else None

    @property
    def failed(self) -> bool:
        return self._failed

    def _start(self) -> None:
        if self._closed:
            raise SessionFailure("SESSION_CLOSED", "native session has been closed")
        if self._failed:
            raise SessionFailure("SESSION_FAILED", "native session is unusable; explicit restart required")
        if self._proc is not None:
            if self._proc.poll() is not None:
                self._invalidate()
                raise SessionFailure("SESSION_EXITED", "native session process exited")
            return
        if self._journal is not None:
            try:
                self._binary_sha256 = hashlib.sha256(self.executable.read_bytes()).hexdigest()
            except OSError as exc:
                self._failed = True
                raise SessionFailure("SESSION_JOURNAL_ERROR", f"cannot identify native binary for journal: {exc}") from exc
        try:
            kwargs: dict[str, Any] = {
                "stdin": subprocess.PIPE,
                "stdout": subprocess.PIPE,
                # Native diagnostics are non-protocol output; keeping the stream
                # detached prevents stderr from contaminating JSONL framing.
                "stderr": subprocess.DEVNULL,
                "text": True,
                "encoding": "utf-8",
                "errors": "strict",
                "bufsize": 1,
            }
            if os.name == "nt":
                kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            self._proc = self._popen_factory([str(self.executable), "session", "--jsonl"], **kwargs)
            if self._proc.stdin is None or self._proc.stdout is None:
                self._invalidate()
                raise SessionFailure("SESSION_START_FAILED", "native session pipes were not created")
            threading.Thread(target=self._read_stdout, name="dl16-session-stdout", daemon=True).start()
            hello = self._request_locked({"command": "hello", "protocol": 1}, timeout_s=5.0)
            protocol = hello.get("protocol")
            if type(protocol) is not int or protocol != 1:
                raise SessionFailure("SESSION_PROTOCOL_ERROR", "native hello must advertise protocol 1")
            commands = hello.get("commands", [])
            self.capabilities = {c for c in commands if isinstance(c, str)} if isinstance(commands, list) else set()
            self._hello = True
        except SessionFailure:
            self._invalidate()
            raise
        except (OSError, UnicodeError, ValueError) as exc:
            self._invalidate()
            raise SessionFailure("SESSION_START_FAILED", str(exc)) from exc

    def _read_stdout(self) -> None:
        proc = self._proc
        if proc is None or proc.stdout is None:
            return
        try:
            while True:
                chunk = proc.stdout.readline(MAX_LINE_BYTES + 1)
                if chunk == "":
                    self._stdout_queue.put(("eof", None))
                    return
                encoded_size = len(chunk.encode("utf-8"))
                if encoded_size > MAX_LINE_BYTES or not chunk.endswith("\n"):
                    # Drain through one line ending so the thread doesn't become a
                    # producer of arbitrary-sized responses. The session is fatal.
                    while chunk and not chunk.endswith("\n"):
                        chunk = proc.stdout.readline(MAX_LINE_BYTES + 1)
                    self._stdout_queue.put(("error", "response line exceeds 65536 bytes or is unterminated"))
                    return
                self._stdout_queue.put(("line", chunk))
        except (OSError, UnicodeError, ValueError) as exc:
            self._stdout_queue.put(("error", str(exc)))

    def _next_response(self, timeout_s: float) -> dict[str, Any]:
        self._pending_raw_response = None
        try:
            kind, payload = self._stdout_queue.get(timeout=timeout_s)
        except queue.Empty as exc:
            self._invalidate()
            raise SessionFailure("SESSION_TIMEOUT", "native session response timed out; request was not replayed") from exc
        if kind == "line":
            self._pending_raw_response = payload[:MAX_LINE_BYTES]
        if kind == "eof":
            code = "SESSION_EXITED"
            proc = self._proc
            detail = f"native session exited (code {proc.poll() if proc else 'unknown'})"
            self._invalidate()
            raise SessionFailure(code, detail)
        if kind == "error":
            self._invalidate()
            raise SessionFailure("SESSION_PROTOCOL_ERROR", str(payload))
        self._pending_raw_response = payload[:MAX_LINE_BYTES]
        try:
            value = json.loads(payload)
        except (json.JSONDecodeError, TypeError) as exc:
            self.last_diagnostics = {"response_preview": str(payload)[:2048],
                                     "response_bytes": len(str(payload).encode("utf-8", errors="replace"))}
            self._observe("protocol_error", self.last_diagnostics)
            self._invalidate()
            raise SessionFailure("SESSION_PROTOCOL_ERROR", f"invalid JSON response: {exc}",
                                 diagnostics=self.last_diagnostics) from exc
        if not isinstance(value, dict):
            self._invalidate()
            raise SessionFailure("SESSION_PROTOCOL_ERROR", "native response must be a JSON object")
        return value

    def _request_locked(self, request: dict[str, Any], *, timeout_s: float) -> dict[str, Any]:
        proc = self._proc
        if proc is None or proc.stdin is None:
            raise SessionFailure("SESSION_START_FAILED", "native session is not running")
        self._counter += 1
        request_id = f"p{proc.pid}-{self._counter}"
        request = {**request, "request_id": request_id}
        encoded = json.dumps(request, ensure_ascii=True, separators=(",", ":"))
        if len(encoded.encode("utf-8")) > MAX_LINE_BYTES:
            raise SessionFailure("SESSION_REQUEST_TOO_LARGE", "request exceeds 65536 bytes")
        started = time.monotonic()
        journal_request = {**request, "binary_sha256": self._binary_sha256,
                           "identity_authority": "file_sha256",
                           "configuration_authority": "caller_requested"}
        self._record_journal({"type": "request", "request_id": request_id,
                              "native_pid": proc.pid, "request": journal_request,
                              "started_monotonic": started})
        try:
            proc.stdin.write(encoded + "\n")
            proc.stdin.flush()
        except (BrokenPipeError, OSError, UnicodeError) as exc:
            self._journal_result(request_id, None, started, "write_error", str(exc))
            self._invalidate()
            raise SessionFailure("SESSION_EXITED", f"failed writing to native session: {exc}") from exc
        try:
            response = self._next_response(timeout_s)
        except SessionFailure as exc:
            self._journal_result(request_id, None, started, exc.code, str(exc),
                                 getattr(self, "_pending_raw_response", None))
            raise
        response_matches = response.get("request_id") == request_id
        self._journal_result(request_id, response, started,
                             ("SESSION_PROTOCOL_ERROR" if not response_matches else
                              "success" if response.get("ok") is True else "native_error"),
                             raw_response=getattr(self, "_pending_raw_response", None),
                             response_request_id=response.get("request_id"),
                             response_native_pid=response.get("native_pid"))
        if not response_matches:
            self.last_diagnostics = {"expected_request_id": request_id,
                                     "actual_request_id": response.get("request_id"),
                                     "response_keys": sorted(response.keys())}
            self._observe("protocol_error", self.last_diagnostics)
            self._invalidate()
            raise SessionFailure("SESSION_PROTOCOL_ERROR", "native response request_id mismatch",
                                 diagnostics=self.last_diagnostics)
        if response.get("ok") is not True:
            raise SessionFailure(str(response.get("error_code", "SESSION_COMMAND_FAILED")),
                                 str(response.get("message", "native command failed")))
        return response

    def _record_journal(self, entry: dict[str, Any]) -> None:
        if self._journal is None:
            return
        self._journal_sequence += 1
        entry = {"schema": "dl16-session-journal/v1", "sequence": self._journal_sequence,
                 "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                 "stderr": {"state": "unavailable", "reason": "redirected to DEVNULL"}, **entry}
        try:
            self._journal.record(entry)
        except OSError as exc:
            self._failed = True
            self._stop_child()
            raise SessionFailure("SESSION_JOURNAL_ERROR", f"session journal write failed: {exc}") from exc

    def _journal_result(self, request_id: str, response: dict[str, Any] | None,
                        started: float, outcome: str, error: str | None = None,
                        raw_response: str | None = None, response_request_id: Any = None,
                        response_native_pid: Any = None) -> None:
        self._record_journal({"type": "result", "request_id": request_id,
                              "response_request_id": response_request_id,
                              "response_native_pid": response_native_pid,
                              "response": response, "raw_response": raw_response,
                              "outcome": outcome, "error": error,
                              "elapsed_ms": round((time.monotonic() - started) * 1000)})

    def _observe(self, event: str, details: dict[str, Any]) -> None:
        if self._observer is None:
            return
        try:
            self._observer({"event": event, "pid": self.pid, **details})
        except Exception:
            pass

    def request(self, request: dict[str, Any], *, timeout_s: float) -> dict[str, Any]:
        with self._lock:
            self._start()
            if not self._hello:
                raise SessionFailure("SESSION_PROTOCOL_ERROR", "native hello handshake missing")
            if request.get("command") == "pwm" and "pwm" not in self.capabilities:
                raise SessionFailure("NATIVE_CAPABILITY_MISSING", "native hello does not advertise PWM; rebuild patched CLI")
            if "raw_rx_path" in request and "raw_rx_log_v1" not in self.capabilities:
                raise SessionFailure("NATIVE_CAPABILITY_MISSING", "native hello does not advertise raw RX logging v1")
            return self._request_locked(request, timeout_s=timeout_s)

    def _invalidate(self) -> None:
        self._failed = True
        cleanup = self._stop_child()
        if self._journal is not None:
            self._record_journal({"type": "cleanup", **cleanup})

    def _stop_child(self) -> dict[str, Any]:
        proc, self._proc = self._proc, None
        if proc is None:
            return {"outcome": "not_started", "pid": None, "returncode": None,
                    "terminate_error": None, "kill_error": None, "stream_errors": []}
        result = {"pid": proc.pid, "returncode": None, "terminate_error": None,
                  "kill_error": None, "stream_errors": []}
        try:
            if proc.poll() is None:
                try:
                    proc.terminate()
                    try:
                        proc.wait(timeout=STOP_GRACE_SECONDS)
                    except subprocess.TimeoutExpired:
                        try:
                            proc.kill()
                            proc.wait(timeout=STOP_GRACE_SECONDS)
                        except (OSError, subprocess.TimeoutExpired) as exc:
                            result["kill_error"] = str(exc)
                except OSError as exc:
                    result["terminate_error"] = str(exc)
            result["returncode"] = proc.poll()
        except OSError as exc:
            result["poll_error"] = str(exc)
        for stream in (proc.stdin, proc.stdout):
            try:
                if stream is not None:
                    stream.close()
            except OSError as exc:
                result["stream_errors"].append(str(exc))
        errors = result.get("terminate_error") or result.get("kill_error") or result.get("poll_error") or result["stream_errors"]
        result["outcome"] = "failed" if errors or result["returncode"] is None else "exited"
        return result

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            evidence_error = None
            if self._proc is not None and not self._failed and self._proc.poll() is None:
                try:
                    self._request_locked({"command": "close"}, timeout_s=STOP_GRACE_SECONDS)
                except SessionFailure as exc:
                    evidence_error = exc
            cleanup = self._stop_child()
            if self._journal is not None:
                try:
                    self._record_journal({"type": "cleanup", **cleanup})
                except SessionFailure as exc:
                    evidence_error = evidence_error or exc
                finally:
                    try:
                        self._journal.close()
                    except OSError as exc:
                        evidence_error = evidence_error or SessionFailure(
                            "SESSION_JOURNAL_ERROR", f"session journal close failed: {exc}")
            self._closed = True
            if evidence_error is not None:
                raise evidence_error


_registered: list[NativeSession] = []


def register_for_shutdown(session: NativeSession) -> None:
    _registered.append(session)


def _close_registered() -> None:
    for session in reversed(_registered):
        session.close()


atexit.register(_close_registered)
