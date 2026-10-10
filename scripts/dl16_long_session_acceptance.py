"""Explicit live-only bounded dynamic acceptance; no reset, replay or fallback."""
import argparse
import json
import os
from pathlib import Path
import sys
import uuid

from dl16_session_smoke import durable_write_json, inspect_capture_validity
from session_waveform_check import check_pwm_bits
from dl16_mcp.session import NativeSession


def run(cli: Path, taskdir: Path, count: int = 20):
    if not 2 <= count <= 20:
        raise ValueError("count must be 2..20")
    root = taskdir.resolve() / ("dynamic-" + uuid.uuid4().hex)
    root.mkdir(parents=True, exist_ok=False)
    prior = os.environ.get("DL16_SESSION_JOURNAL_DIR")
    os.environ["DL16_SESSION_JOURNAL_DIR"] = str(root / "journal")
    result = {"task": "DL16-TASK-032", "steps": [], "verdict": "FAILED", "run_dir": str(root)}
    session = None
    try:
        session = NativeSession(cli)
        for output, frequency in ((0, 1000), (1, 2000)):
            response = session.request({"command": "pwm", "op": "configure", "output": output,
                                        "frequency_hz": frequency, "duty_percent": 50}, timeout_s=10)
            durable_write_json(root / f"source-{output}.json", response)
        for index in range(count):
            request = {"command": "capture", "channels": [8, 14], "sample_rate_hz": 20000000,
                       "duration_ms": 10, "threshold_voltage": 1.6, "trigger": "immediate",
                       "trigger_position_percent": 10, "trigger_timeout_sec": 3,
                       "output_dir": str(root / "captures")}
            record = {"step": index + 1, "request": request, "state": "dispatching"}
            path = root / f"step-{index + 1}.json"
            durable_write_json(path, record)
            response = session.request(request, timeout_s=10)
            record["response"] = response
            capture = response["result"]
            artifact = Path(capture["artifact_dir"])
            metadata = json.loads((artifact / "meta.json").read_text())
            record["capture_validity"] = inspect_capture_validity(capture, metadata)
            record["waveform"] = {str(ch): check_pwm_bits(artifact / f"ch{ch:02}.bits", 200000,
                                                        20000000, hz)
                                  for ch, hz in ((8, 1000), (14, 2000))}
            record["state"] = "passed" if (record["capture_validity"]["valid"] and
                capture.get("cleanup_stop_attempted") is True and capture.get("cleanup_stop_ok") is True and
                all(v["valid"] for v in record["waveform"].values())) else "failed"
            durable_write_json(path, record)
            result["steps"].append(record)
            if record["state"] != "passed":
                break
        if len(result["steps"]) == count and all(r["state"] == "passed" for r in result["steps"]):
            result["verdict"] = "PASS_WAVEFORM_UNCALIBRATED"
    except Exception as exc:
        result["error"] = {"type": type(exc).__name__, "message": str(exc)}
    finally:
        try:
            if session is not None:
                session.close()
            result["cleanup"] = "close_returned"
        except Exception as exc:
            result["cleanup"] = str(exc)
            result["verdict"] = "CLEANUP_FAILED"
        finally:
            if prior is None:
                os.environ.pop("DL16_SESSION_JOURNAL_DIR", None)
            else:
                os.environ["DL16_SESSION_JOURNAL_DIR"] = prior
        durable_write_json(root / "result.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cli", type=Path, required=True)
    parser.add_argument("--taskdir", type=Path, required=True)
    parser.add_argument("--confirm-safe-connected-ch8-ch14", action="store_true")
    args = parser.parse_args()
    if not args.confirm_safe_connected_ch8_ch14:
        parser.error("explicit current safe hardware confirmation required")
    doc = run(args.cli.resolve(), args.taskdir)
    print(json.dumps({k: v for k, v in doc.items() if k != "steps"}, indent=2))
    sys.exit(0 if doc["verdict"] == "PASS_WAVEFORM_UNCALIBRATED" else 1)
