"""Owner for one persistent native JSONL worker process.

The manager serializes every request, correlates request IDs, and never replays a
request after an ambiguous worker/protocol failure. It owns only the child it starts.
"""
from __future__ import annotations

import atexit
import json
import os
from pathlib import Path
import queue
import subprocess
import threading
import time
from typing import Any, Callable

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
        self._observer = observer
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
            self._request_locked({"command": "hello", "protocol": 1}, timeout_s=5.0)
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
        try:
            kind, payload = self._stdout_queue.get(timeout=timeout_s)
        except queue.Empty as exc:
            self._invalidate()
            raise SessionFailure("SESSION_TIMEOUT", "native session response timed out; request was not replayed") from exc
        if kind == "eof":
            code = "SESSION_EXITED"
            proc = self._proc
            detail = f"native session exited (code {proc.poll() if proc else 'unknown'})"
            self._invalidate()
            raise SessionFailure(code, detail)
        if kind == "error":
            self._invalidate()
            raise SessionFailure("SESSION_PROTOCOL_ERROR", str(payload))
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
        try:
            proc.stdin.write(encoded + "\n")
            proc.stdin.flush()
        except (BrokenPipeError, OSError, UnicodeError) as exc:
            self._invalidate()
            raise SessionFailure("SESSION_EXITED", f"failed writing to native session: {exc}") from exc
        response = self._next_response(timeout_s)
        if response.get("request_id") != request_id:
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
            return self._request_locked(request, timeout_s=timeout_s)

    def _invalidate(self) -> None:
        self._failed = True
        self._stop_child()

    def _stop_child(self) -> None:
        proc, self._proc = self._proc, None
        if proc is None:
            return
        try:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=STOP_GRACE_SECONDS)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=STOP_GRACE_SECONDS)
        except (OSError, subprocess.TimeoutExpired):
            pass
        for stream in (proc.stdin, proc.stdout):
            try:
                if stream is not None:
                    stream.close()
            except OSError:
                pass

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            if self._proc is not None and not self._failed and self._proc.poll() is None:
                try:
                    self._request_locked({"command": "close"}, timeout_s=STOP_GRACE_SECONDS)
                except SessionFailure:
                    pass
            self._stop_child()
            self._closed = True


_registered: list[NativeSession] = []


def register_for_shutdown(session: NativeSession) -> None:
    _registered.append(session)


def _close_registered() -> None:
    for session in reversed(_registered):
        session.close()


atexit.register(_close_registered)
