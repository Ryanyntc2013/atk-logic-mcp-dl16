import numpy as np
import pytest
from dl16_mcp.analysis import (AnalysisError, digital_edges, digital_transitions,
                               glitch_filter, measure_pwm, measure_skew, search_conditions,
                               to_edges_csv, to_samples_csv, to_vcd)
from dl16_mcp.artifacts import Waveform


def wave(ch, samples, rate=20_000_000, integrity="COMPLETE"):
    return Waveform(ch, np.packbits(np.asarray(samples, dtype=np.uint8), bitorder="little").tobytes(),
                    len(samples), rate, integrity, "SYNTHETIC", {})


def pulse(n=20_000, period=200, shift=0, missing=None):
    x = np.zeros(n, dtype=np.uint8)
    for k, pos in enumerate(range(100 + shift, n - 100, period)):
        if k == missing:
            continue
        x[pos:pos + 20] = 1
    return x


def test_edges_lsb_first_and_end_padding():
    w = wave(0, [0, 0, 1, 1, 0, 1, 0, 0, 1])
    assert digital_edges(w.raw, w.samples).tolist() == [2, 5, 8]
    assert digital_edges(w.raw, w.samples, rising=False).tolist() == [4, 6]


def test_skew_positive_250ns_and_waveform_pass():
    a = wave(3, pulse())
    b = wave(7, pulse(shift=5))
    r = measure_skew(a, b, max_abs_error_ns=1000)
    assert r["matched_pairs"] > 90
    assert r["delay"]["median_ns"] == pytest.approx(250.0)
    assert r["missing_target_pulses"] == 0
    assert r["verdict"] == "PASS_WAVEFORM"


def test_skew_negative_delay():
    a = wave(3, pulse(shift=6))
    b = wave(7, pulse(shift=1))
    r = measure_skew(a, b, max_abs_error_ns=1000)
    assert r["delay"]["median_ns"] == pytest.approx(-250.0)


def test_missing_pulse_forces_fail():
    a = wave(3, pulse())
    b = wave(7, pulse(shift=4, missing=12))
    r = measure_skew(a, b, max_abs_error_ns=1000)
    assert r["missing_target_pulses"] == 1
    assert r["verdict"] == "FAIL_WAVEFORM"


def test_failed_tolerance():
    r = measure_skew(wave(3, pulse()), wave(7, pulse(shift=30)), max_abs_error_ns=1000)
    assert r["verdict"] == "FAIL_WAVEFORM"


def test_quality_gate():
    r = measure_skew(wave(3, pulse(), integrity="UNVERIFIED"), wave(7, pulse(shift=5)),
                     max_abs_error_ns=1000)
    assert r["verdict"] == "NOT_EVALUATED"


def test_no_reference_pulses():
    with pytest.raises(AnalysisError):
        measure_skew(wave(3, np.zeros(100)), wave(7, np.zeros(100)))


def test_pwm_median_period():
    r = measure_pwm(wave(3, pulse()))
    assert r["frequency_hz_median"] == pytest.approx(100_000.0)


def test_across_chunk_boundaries():
    x = np.zeros(128 * 1024 * 8 + 100, dtype=np.uint8)
    x[128 * 1024 * 8 - 1:] = 1
    w = wave(3, x)
    assert digital_edges(w.raw, w.samples).tolist() == [128 * 1024 * 8 - 1]


def test_digital_transitions_ordered_levels():
    w = wave(0, [0, 0, 1, 1, 0, 1, 0])
    idx, lvl = digital_transitions(w.raw, w.samples)
    assert idx.tolist() == [2, 4, 5, 6]
    assert lvl.tolist() == [1, 0, 1, 0]


def test_to_edges_csv_lsb_first_and_times():
    w = wave(0, [0, 0, 1, 1, 0, 1, 0, 0, 1], rate=20_000_000)
    lines = to_edges_csv(w, polarity="rising").strip().splitlines()
    assert lines[0] == "sample,time_ns,level"
    assert lines[1] == "2,100,1"
    assert "5,250,1" in lines
    falling = to_edges_csv(w, polarity="falling").strip().splitlines()
    assert falling[1] == "4,200,0"


def test_to_vcd_is_edge_based_with_initial_level():
    w = wave(3, [0, 1, 1, 0], rate=20_000_000)
    vcd = to_vcd(w)
    assert "$timescale 1ns $end" in vcd
    assert "$var wire 1 ! ch3 $end" in vcd
    lines = vcd.strip().splitlines()
    assert "#0" in lines and "0!" in lines
    assert "#50" in lines and "#150" in lines  # 20 MHz -> 50 ns/sample
    assert lines[-1] == "0!"  # final fall back to low


def _bits(w):
    return np.unpackbits(np.frombuffer(w.raw, dtype=np.uint8), bitorder="little")[:w.samples]


def test_glitch_filter_removes_short_pulses():
    w = wave(0, [1, 1, 1, 0, 1, 1, 1, 1])
    filtered, removed = glitch_filter(w.raw, w.samples, min_pulse_samples=3)
    got = np.unpackbits(np.frombuffer(filtered, dtype=np.uint8), bitorder="little")[:8]
    assert got.tolist() == [1] * 8
    assert removed == 1


def test_glitch_filter_combined_edge_cap_is_not_twice_max_edges():
    # 4 rising + 4 falling. A per-polarity budget of 4 would accept all 8.
    bits = [0, 1] * 4 + [0]
    raw = np.packbits(np.asarray(bits, dtype=np.uint8), bitorder="little").tobytes()
    with pytest.raises(AnalysisError, match="Too many edges"):
        digital_transitions(raw, len(bits), max_edges=4)
    with pytest.raises(AnalysisError, match="Too many"):
        glitch_filter(raw, len(bits), min_pulse_samples=1, max_edges=4)
    short = [0, 1, 0, 1, 0]
    short_raw = np.packbits(np.asarray(short, dtype=np.uint8), bitorder="little").tobytes()
    idx, _ = digital_transitions(short_raw, len(short), max_edges=4)
    assert len(idx) == 4


def test_glitch_filter_leading_short_run_takes_next_level():
    w = wave(0, [1, 0, 0, 0])
    filtered, removed = glitch_filter(w.raw, w.samples, min_pulse_samples=3)
    got = np.unpackbits(np.frombuffer(filtered, dtype=np.uint8), bitorder="little")[:4]
    assert got.tolist() == [0, 0, 0, 0]
    assert removed == 1


def test_search_conditions_and_semantics():
    ch0 = wave(0, [0, 0, 1, 1, 0, 0, 0, 0])
    ch1 = wave(1, [0, 0, 1, 1, 1, 1, 0, 0])
    waves = {0: ch0, 1: ch1}
    r = search_conditions(waves, [(0, "rising"), (1, "high")])
    assert r["total_matches"] == 1
    assert r["matches"][0]["sample"] == 2
    assert search_conditions(waves, [(0, "rising"), (1, "low")])["total_matches"] == 0
    assert search_conditions(waves, [(1, "high")])["total_matches"] == 4


def test_to_samples_csv_full_and_bounded():
    w = wave(0, [0, 1, 1, 0], rate=20_000_000)
    lines = to_samples_csv(w).strip().splitlines()
    assert lines[0] == "sample,time_ns,level"
    assert lines[1] == "0,0,0"
    assert lines[2] == "1,50,1"
    assert lines[-1] == "3,150,0"
    try:
        to_samples_csv(w, max_samples=2)
    except AnalysisError:
        pass
    else:
        raise AssertionError("expected AnalysisError for oversized sample export")
