import json
from pathlib import Path

import numpy as np

from dl16_mcp import service


def _make_capture(root: Path, cid: str, bits: bytes, samples: int) -> None:
    cdir = root / "captures" / cid
    cdir.mkdir(parents=True)
    (cdir / "ch00.bits").write_bytes(bits)
    (cdir / "meta.json").write_text(json.dumps({
        "sample_rate": 20_000_000,
        "requested_samples": samples,
        "sample_counts": {"0": samples},
        "data_integrity": "COMPLETE",
        "capture_complete_received": True,
        "trigger_ack_received": True,
        "evidence_source": "SYNTHETIC",
    }), encoding="utf-8")


def test_logic_export_vcd_and_edges(monkeypatch, tmp_path):
    monkeypatch.setenv("DL16_DATA_DIR", str(tmp_path))
    bits = np.packbits(np.array([0, 0, 1, 0, 1, 0, 0, 0], dtype=np.uint8),
                       bitorder="little").tobytes()
    _make_capture(tmp_path, "cap_test", bits, 8)

    vcd = service.logic_export("cap_test", 0, "vcd")
    assert vcd["success"] is True
    assert Path(vcd["path"]).is_file()
    assert Path(vcd["path"]).read_text(encoding="utf-8").startswith("$timescale")

    edges = service.logic_export("cap_test", 0, "edges")
    assert edges["success"] is True
    header = Path(edges["path"]).read_text(encoding="utf-8").splitlines()[0]
    assert header == "sample,time_ns,level"

    bad = service.logic_export("cap_test", 0, "bogus")
    assert bad["success"] is False and bad["error_code"] == "EXPORT_FAILED"


def test_logic_export_rejects_traversal_name(monkeypatch, tmp_path):
    monkeypatch.setenv("DL16_DATA_DIR", str(tmp_path))
    bits = np.packbits(np.array([0, 1, 0, 1], dtype=np.uint8), bitorder="little").tobytes()
    _make_capture(tmp_path, "cap_test2", bits, 4)
    r = service.logic_export("cap_test2", 0, "vcd", out_name="../escape.vcd")
    assert r["success"] is False


def test_logic_export_overwrite_protection(monkeypatch, tmp_path):
    monkeypatch.setenv("DL16_DATA_DIR", str(tmp_path))
    bits = np.packbits(np.array([0, 1, 0, 1], dtype=np.uint8), bitorder="little").tobytes()
    _make_capture(tmp_path, "cap_ow", bits, 4)
    assert service.logic_export("cap_ow", 0, "samples")["success"] is True
    again = service.logic_export("cap_ow", 0, "samples")
    assert again["success"] is False and "exists" in again["message"]
    forced = service.logic_export("cap_ow", 0, "samples", overwrite=True)
    assert forced["success"] is True
