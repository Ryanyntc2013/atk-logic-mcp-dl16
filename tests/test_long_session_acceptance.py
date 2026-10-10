import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import dl16_long_session_acceptance as acceptance


def test_source_error_is_recorded_and_closed(tmp_path, monkeypatch):
    calls = []

    class FakeSession:
        def __init__(self, path):
            pass

        def request(self, request, timeout_s):
            calls.append(request)
            raise RuntimeError("source rejected")

        def close(self):
            calls.append("closed")

    monkeypatch.setattr(acceptance, "NativeSession", FakeSession)
    monkeypatch.setenv("DL16_SESSION_JOURNAL_DIR", "original")
    doc = acceptance.run(tmp_path / "binary", tmp_path)
    assert doc["verdict"] == "FAILED"
    assert len(calls) == 2 and calls[-1] == "closed"
    assert (Path(doc["run_dir"]) / "result.json").is_file()
    assert acceptance.os.environ["DL16_SESSION_JOURNAL_DIR"] == "original"


def test_invalid_count_does_not_create_run(tmp_path):
    with pytest.raises(ValueError):
        acceptance.run(tmp_path / "binary", tmp_path, count=21)
    assert not list(tmp_path.iterdir())
