import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("observed_smoke", ROOT / "scripts" / "dl16_session_smoke.py")
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


def test_complete_and_ack_without_samples_never_pass_observed_sequence():
    vector = json.loads((ROOT / "tests" / "vectors" / "task023-complete-before-data.json").read_text())
    assert vector["orders"] == [6, 6, 6, 4, 5, 5, 5, 5]
    assert 1 not in vector["orders"]
    # Even misleading success/COMPLETE flags cannot replace numeric sample evidence.
    result = {
        "success": True, "data_integrity": "COMPLETE",
        "trigger_ack_received": True, "capture_complete_received": True,
        "actual_samples_per_channel": vector["samples_after_crop"],
    }
    meta = {
        **result, "channels": vector["requested_channels"],
        "sample_counts": vector["samples_after_crop"],
        "sample_rate": 20000000, "duration_ms": 10,
    }
    verdict = smoke.inspect_capture_validity(result, meta)
    assert verdict["valid"] is vector["expected_valid"]
    assert any("samples" in reason for reason in verdict["reasons"])
