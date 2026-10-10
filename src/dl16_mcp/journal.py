"""Opt-in, append-only JSONL evidence journal for persistent native sessions."""
from __future__ import annotations

import json
import os
from pathlib import Path
import threading
import uuid
from typing import Any

# Raw JSONL and parsed response coexist; JSON escaping can expand either copy.
MAX_RECORD_BYTES = 1024 * 1024


class SessionJournal:
    def __init__(self, directory: Path):
        self.directory = Path(directory)
        self._lock = threading.Lock()
        self._file = None
        self.path: Path | None = None

    def _ensure_open(self) -> None:
        if self._file is not None:
            return
        if not self.directory.exists():
            self.directory.mkdir(parents=True, exist_ok=True)
        if not self.directory.is_dir():
            raise OSError(f"journal path is not a directory: {self.directory}")
        for _ in range(10):
            path = self.directory / f"dl16-session-{uuid.uuid4().hex}.jsonl"
            try:
                self._file = path.open("x", encoding="utf-8", newline="\n")
                self.path = path
                return
            except FileExistsError:
                continue
        raise OSError("unable to allocate unique session journal file")

    def record(self, record: dict[str, Any]) -> None:
        payload = json.dumps(record, ensure_ascii=True, separators=(",", ":"))
        if len(payload.encode("utf-8")) > MAX_RECORD_BYTES:
            raise OSError("session journal record exceeds 1 MiB")
        with self._lock:
            self._ensure_open()
            self._file.write(payload + "\n")
            self._file.flush()
            os.fsync(self._file.fileno())

    def close(self) -> None:
        with self._lock:
            if self._file is not None:
                self._file.close()
                self._file = None
