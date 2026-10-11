import json
import zipfile
import pytest
from dl16_mcp.artifacts import load_atkdl, load_capture


def test_native_archive_safety(monkeypatch, tmp_path):
    monkeypatch.setenv("DL16_DATA_DIR", str(tmp_path))
    with pytest.raises(ValueError):
        load_capture("../other", 0)


def test_verified_native_capture(monkeypatch, tmp_path):
    monkeypatch.setenv("DL16_DATA_DIR", str(tmp_path))
    d = tmp_path / "captures" / "example"
    d.mkdir(parents=True)
    (d / "ch03.bits").write_bytes(b"\x5a" * 10)
    (d / "meta.json").write_text(json.dumps({"sample_rate": 20_000_000,
      "data_integrity": "COMPLETE", "capture_complete_received": True,
      "trigger_ack_received": True, "requested_samples": 80, "sample_counts": {"3": 80},
      "evidence_source": "REAL_HARDWARE"}), encoding="utf-8")
    w = load_capture("example", 3)
    assert w.integrity == "COMPLETE"
    assert w.samples == 80


def test_vendor_archive_is_never_promoted_to_live_hardware(tmp_path):
    file = tmp_path / "example.atkdl"
    with zipfile.ZipFile(file, "w") as z:
        z.writestr("3/3-0.bin", b"\x00" * 250)
        z.writestr("set.ini", 'settingData={"setHz":1000000,"setTime":2}\n')
    w = load_atkdl(file, 3)
    assert w.integrity == "OFFLINE_LENGTH_MATCH"
    assert w.source == "SAVED_ATKDL"


def test_split_vendor_archive(tmp_path):
    file = tmp_path / "split.atkdl"
    with zipfile.ZipFile(file, "w") as z:
        z.writestr("3/3-0.bin", b"\x00" * 100)
        z.writestr("3/3-1.bin", b"\xff" * 150)
        z.writestr("set.ini", 'settingData={"setHz":1000000,"setTime":2}\n')
    w = load_atkdl(file, 3)
    assert len(w.raw) == 250
    assert w.samples == 2000


def test_load_stream_capture(monkeypatch, tmp_path):
    monkeypatch.setenv("DL16_DATA_DIR", str(tmp_path))
    d = tmp_path / "captures" / "stream-test"
    d.mkdir(parents=True)
    (d / "ch8.packed.bin").write_bytes(b"\xaa" * 100)
    (d / "stream_meta.json").write_text(json.dumps({
        "schema": "dl16-incremental-packed/v1",
        "sample_rate_hz": 1_000_000,
        "data_integrity": "INCOMPLETE",
        "evidence_source": "SYNTHETIC_OFFLINE",
        "channels": [{"channel": 8, "stored_bytes": 100}],
    }), encoding="utf-8")
    w = load_capture("stream-test", 8)
    assert w.channel == 8
    assert w.samples == 800
    assert w.sample_rate_hz == 1_000_000
    assert w.integrity == "INCOMPLETE"
    assert w.source == "SYNTHETIC_OFFLINE"

    with pytest.raises(FileNotFoundError):
        load_capture("stream-test", 9)

