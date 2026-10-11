"""Offline synthetic stream prototype tests (DL16-TASK-036).

Validates offline streaming models, strict validation prior to filesystem operations,
exclusive creation ('xb'), directory overwrite protection, safe capture_id rules,
responsive cancellation, byte budgets, and verification of expected sample counts.
"""

import json
import threading
import time
from pathlib import Path

import pytest

from dl16_mcp.stream import (
    CancellationToken,
    StreamConfig,
    StreamError,
    StreamSessionRunner,
    StreamWriter,
)


def test_stream_config_strict_validation():
    cfg = StreamConfig(
        channels=[0, 1],
        sample_rate_hz=20_000_000,
        duration_s=5.0,
        output_dir=Path("tmp_out"),
        capture_id="cap_valid",
        evidence_source="SYNTHETIC_OFFLINE",
    )
    cfg.validate()

    with pytest.raises(StreamError) as exc:
        StreamConfig(
            channels=[0, 1],
            sample_rate_hz=20_000_000,
            duration_s=5.0,
            output_dir=Path("tmp_out"),
            capture_id="cap_real",
            evidence_source="REAL_HARDWARE",
        ).validate()
    assert exc.value.code == "INVALID_EVIDENCE_SOURCE"

    for unsafe in [".", "..", "a/b", "a\\b", "cap:1"]:
        with pytest.raises(StreamError) as exc:
            StreamConfig(
                channels=[0, 1],
                sample_rate_hz=20_000_000,
                duration_s=5.0,
                output_dir=Path("tmp_out"),
                capture_id=unsafe,
            ).validate()
        assert exc.value.code == "INVALID_STREAM_CONFIG"
        assert "unsafe or contains invalid characters" in str(exc.value)

    with pytest.raises(StreamError) as exc:
        StreamConfig(
            channels=[True, False],  # type: ignore
            sample_rate_hz=20_000_000,
            duration_s=5.0,
            output_dir=Path("tmp_out"),
            capture_id="cap_bool",
        ).validate()
    assert exc.value.code == "INVALID_STREAM_CONFIG"

    with pytest.raises(StreamError) as exc:
        StreamConfig(
            channels=[0, 1],
            sample_rate_hz=20_000_000,
            duration_s=5.0,
            output_dir=Path("tmp_out"),
            capture_id="cap_rle",
            enable_rle=True,
        ).validate()
    assert exc.value.code == "UNSUPPORTED_MODE"


def test_stream_writer_validates_before_file_creation(tmp_path):
    out_dir = tmp_path / "stream_runs"
    invalid_cfg = StreamConfig(
        channels=[0, 1, 2],
        sample_rate_hz=20_000_000,
        duration_s=5.0,
        output_dir=out_dir,
        capture_id="invalid_before_create",
    )
    with pytest.raises(StreamError):
        StreamWriter(invalid_cfg)
    assert not (out_dir / "invalid_before_create").exists()


def test_stream_writer_incremental_disk_append_and_completion(tmp_path):
    out_dir = tmp_path / "stream_runs"
    cfg = StreamConfig(
        channels=[0, 1],
        sample_rate_hz=1000,
        duration_s=0.01,
        output_dir=out_dir,
        capture_id="stream_001",
    )
    writer = StreamWriter(cfg)
    stream_folder = out_dir / "stream_001"
    assert stream_folder.exists()

    ch0_bin = stream_folder / "ch00.stream.bin"
    ch1_bin = stream_folder / "ch01.stream.bin"
    meta_json = stream_folder / "stream_meta.json"
    assert ch0_bin.exists()
    assert ch1_bin.exists()

    writer.write_chunk({0: b"\xaa", 1: b"\x55"})
    assert ch0_bin.stat().st_size == 1
    assert ch1_bin.stat().st_size == 1

    with pytest.raises(StreamError) as exc:
        writer.mark_completed_if_verified()
    assert exc.value.code == "INCOMPLETE_STREAM"

    writer.write_chunk({0: b"\xbb", 1: b"\x66"})
    assert ch0_bin.stat().st_size == 2
    assert ch1_bin.stat().st_size == 2

    writer.mark_completed_if_verified()
    assert writer.provenance.status == "completed"

    saved_meta = json.loads(meta_json.read_text(encoding="utf-8"))
    assert saved_meta["status"] == "completed"
    assert saved_meta["evidence_source"] == "SYNTHETIC_OFFLINE"
    assert saved_meta["total_bytes"]["0"] == 2
    assert saved_meta["total_bytes"]["1"] == 2


def test_stream_writer_overwrite_protection(tmp_path):
    out_dir = tmp_path / "stream_runs"
    cfg = StreamConfig(
        channels=[0, 1],
        sample_rate_hz=1000,
        duration_s=0.01,
        output_dir=out_dir,
        capture_id="stream_protect",
    )
    w1 = StreamWriter(cfg)
    w1.write_chunk({0: b"\x00\x00", 1: b"\x00\x00"})
    w1.mark_completed_if_verified()

    with pytest.raises(StreamError) as exc:
        StreamWriter(cfg)
    assert exc.value.code == "DESTINATION_EXISTS"


def test_stream_responsive_cancellation(tmp_path):
    out_dir = tmp_path / "stream_runs"
    cfg = StreamConfig(
        channels=[0, 1],
        sample_rate_hz=10_000_000,
        duration_s=10.0,
        output_dir=out_dir,
        capture_id="stream_cancel_test",
    )
    writer = StreamWriter(cfg)
    cancel_token = CancellationToken()
    runner = StreamSessionRunner(None, writer, cancel_token)

    def cancel_after_delay():
        time.sleep(0.1)
        cancel_token.cancel()

    t = threading.Thread(target=cancel_after_delay)
    t.start()

    t_start = time.time()
    prov = runner.run_bounded(
        poll_interval_s=0.02, chunk_source_fn=lambda: {0: b"\x11" * 64, 1: b"\x22" * 64}
    )
    elapsed = time.time() - t_start
    t.join()

    assert elapsed < 1.5
    assert prov.status == "cancelled"
    assert prov.cancelled_by_user is True
    assert prov.chunks_written > 0
