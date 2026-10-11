"""Depth-comparison observations; hypotheses only, never crop rules."""
import hashlib
import json
from pathlib import Path

from protocol_reference import compute_crc32, convert_to_pc
from task051_observation import CAP, observe


def profile(directory):
    directory = Path(directory)
    result = observe(directory)
    result["schema"] = "task053-stream-depth-observation/v1"
    result["evidence_source"] = "OFFLINE_ANALYSIS_OF_PARENT_CAPTURE"
    summary = json.loads((directory / "summary.json").read_text())
    result["requested_samples"] = summary["requested_samples"]
    result["duration_ms"] = summary["duration_ms"]
    result["sample_rate_hz"] = summary["sample_rate_hz"]
    result["requested_channels"] = summary["channels"]
    path = directory / "orders.jsonl"
    if path.stat().st_size > CAP:
        raise ValueError("orders cap")
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    result["device_profile"] = next(row for row in rows if row.get("kind") == "device_profile")
    result["tx"] = []
    for row in rows:
        if row.get("kind") not in ("parameter", "trigger"):
            continue
        transport = bytes.fromhex(row["transport_hex"])
        linear = convert_to_pc(transport)
        command, length = linear[9:11]
        payload = linear[11:10 + length]
        end = 10 + length
        crc = int.from_bytes(linear[end+1:end+5], "little")
        if linear[8] != 10 or linear[end] != 11 or compute_crc32(linear[9:end]) != crc:
            raise ValueError("TX frame/CRC")
        result["tx"].append({"kind": row["kind"], "authority": row["authority"],
            "command": command, "payload_hex": payload.hex(),
            "transport_sha256": hashlib.sha256(transport).hexdigest()})
    offsets = [event for event in result["events"] if event["order"] == 3]
    payload = bytes.fromhex(offsets[0]["payload_hex"])
    result["order3_trigger_offset"] = int.from_bytes(payload[2:7], "little")
    result["order3_channel_count_fields"] = [int.from_bytes(payload[7+5*i:12+5*i], "little") for i in range(16)]
    for channel in result["channels"]:
        data = (directory / f"channel_{channel['channel']}.packed").read_bytes()
        suffix = len(data) - len(data.rstrip(b"\xaa"))
        channel["observed_aa_suffix_bytes"] = suffix
        channel["excess_over_requested_bytes"] = len(data) - summary["requested_samples"] // 8
        count = result["order3_channel_count_fields"][channel["channel"]]
        channel["count_times_two_plus_six_matches"] = len(data) == count * 2 + 6
    return result


if __name__ == "__main__":
    import sys
    print(json.dumps(profile(sys.argv[1]), indent=2))
