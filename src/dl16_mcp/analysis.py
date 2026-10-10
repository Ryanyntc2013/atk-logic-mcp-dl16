"""Pure offline signal analysis. No native library, USB or MCP imports required."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any
import math

import numpy as np

from .artifacts import Waveform


class AnalysisError(ValueError):
    pass


def digital_edges(raw: bytes, sample_count: int, *, rising: bool = True,
                  max_edges: int = 2_000_000) -> np.ndarray:
    """Return sample indices of rising/falling edges, bit 0 first in each byte.

    Chunked unpacking bounds peak memory for large captures. Includes transitions
    between chunks, and never counts trailing padding bits as samples.
    """
    if sample_count < 0 or sample_count > len(raw) * 8:
        raise AnalysisError("Invalid sample count for packed waveform")
    if max_edges < 1:
        raise AnalysisError("max_edges must be positive")
    if sample_count == 0:
        return np.empty(0, dtype=np.int64)
    all_edges: list[np.ndarray] = []
    last_bit: int | None = None
    edges_total = 0
    bits_seen = 0
    chunk_bytes = 128 * 1024
    for offset in range(0, len(raw), chunk_bytes):
        if bits_seen >= sample_count:
            break
        chunk = raw[offset:offset + chunk_bytes]
        bits = np.unpackbits(np.frombuffer(chunk, dtype=np.uint8), bitorder="little")
        bits = bits[:sample_count - bits_seen]
        if not bits.size:
            break
        transitions = np.flatnonzero(np.diff(bits.astype(np.int8)) == (1 if rising else -1)) + 1
        if last_bit is not None and int(bits[0]) - last_bit == (1 if rising else -1):
            transitions = np.concatenate((np.array([0], dtype=np.int64), transitions))
        if transitions.size:
            all_edges.append(transitions.astype(np.int64) + bits_seen)
            edges_total += transitions.size
            if edges_total > max_edges:
                raise AnalysisError("Too many edges: narrow the analysis window or increase max_edges")
        bits_seen += bits.size
        last_bit = int(bits[-1])
    return np.concatenate(all_edges) if all_edges else np.empty(0, dtype=np.int64)


def _summary_ns(values_ns: np.ndarray) -> dict[str, float]:
    return {"min_ns": float(np.min(values_ns)),
            "max_ns": float(np.max(values_ns)),
            "mean_ns": float(np.mean(values_ns)),
            "median_ns": float(np.median(values_ns)),
            "std_ns": float(np.std(values_ns)),
            "p95_abs_ns": float(np.percentile(np.abs(values_ns), 95)),
            "p99_abs_ns": float(np.percentile(np.abs(values_ns), 99)),
            "max_abs_ns": float(np.max(np.abs(values_ns)))}


def measure_skew(reference: Waveform, target: Waveform, *,
                 polarity: str = "rising", expected_delay_ns: float = 0.0,
                 match_window_ns: float | None = None,
                 max_abs_error_ns: float | None = None,
                 max_edges: int = 2_000_000) -> dict[str, Any]:
    """Pair each reference edge with at most one target edge in time order.

    Delay is t(target) - t(reference). Error is delay - expected_delay_ns.
    Matching window should be wider than expected jitter but less than half a
    pulse period. Returns a waveform verdict, never a device certification.
    """
    if polarity not in ("rising", "falling"):
        raise AnalysisError("polarity must be rising or falling")
    if reference.channel == target.channel:
        raise AnalysisError("Reference and target must be distinct channels")
    if abs(reference.sample_rate_hz - target.sample_rate_hz) > max(1e-6, reference.sample_rate_hz * 1e-12):
        raise AnalysisError("Channel sample rates differ")
    if reference.samples != target.samples:
        raise AnalysisError("Channels have different valid sample counts")
    sr = reference.sample_rate_hz
    if sr <= 0 or not math.isfinite(sr):
        raise AnalysisError("Invalid sample rate")
    if not math.isfinite(expected_delay_ns):
        raise AnalysisError("Invalid expected delay")
    rising = polarity == "rising"
    ref_edges = digital_edges(reference.raw, reference.samples, rising=rising, max_edges=max_edges)
    tar_edges = digital_edges(target.raw, target.samples, rising=rising, max_edges=max_edges)
    period = np.diff(ref_edges)
    if match_window_ns is None:
        if not period.size:
            raise AnalysisError("At least two reference pulses needed to infer matching window")
        match_window_samples = max(1, int(float(np.median(period)) * 0.45))
        window_ns = match_window_samples / sr * 1e9
    else:
        if not math.isfinite(match_window_ns) or match_window_ns <= 0:
            raise AnalysisError("match_window_ns must be positive and finite")
        window_ns = float(match_window_ns)
        match_window_samples = window_ns * sr / 1e9
    expected_samples = expected_delay_ns * sr / 1e9
    # Monotonic nearest-neighbor matching; uniquely consumes target pulses.
    j = 0
    pairs: list[tuple[int, int]] = []
    for ri in ref_edges:
        ideal = float(ri) + expected_samples
        while j < len(tar_edges) and tar_edges[j] < ideal - match_window_samples:
            j += 1
        options = [k for k in (j, j + 1) if k < len(tar_edges)
                   and abs(float(tar_edges[k]) - ideal) <= match_window_samples]
        if options:
            best = min(options, key=lambda k: abs(float(tar_edges[k]) - ideal))
            pairs.append((int(ri), int(tar_edges[best])))
            j = best + 1
    result: dict[str, Any] = {
        "reference_channel": reference.channel, "target_channel": target.channel,
        "sample_rate_hz": sr, "sample_resolution_ns": 1e9 / sr,
        "polarity": polarity, "expected_delay_ns": expected_delay_ns,
        "match_window_ns": window_ns, "reference_edges": len(ref_edges),
        "target_edges": len(tar_edges), "matched_pairs": len(pairs),
        "missing_target_pulses": len(ref_edges) - len(pairs),
        "unmatched_target_pulses": len(tar_edges) - len(pairs),
        "reference_integrity": reference.integrity, "target_integrity": target.integrity,
        "evidence_source": reference.source, "verdict": "NOT_EVALUATED",
    }
    if not pairs:
        result["message"] = "No matched pulse pairs; cannot evaluate timing"
        return result
    samples = np.array(pairs, dtype=np.int64)
    delays = (samples[:, 1].astype(np.float64) - samples[:, 0]) * 1e9 / sr
    errors = delays - expected_delay_ns
    result["delay"] = _summary_ns(delays)
    result["error"] = _summary_ns(errors)
    result["preview_pairs"] = [
        {"reference_sample": int(a), "target_sample": int(b),
         "delay_ns": float(d)} for (a, b), d in zip(pairs[:20], delays[:20])
    ]
    verified_inputs = (reference.integrity == "COMPLETE" and target.integrity == "COMPLETE")
    result["quality_warnings"] = []
    if not verified_inputs:
        result["quality_warnings"].append("Capture metadata not verified as complete")
    if max_abs_error_ns is not None:
        if not math.isfinite(max_abs_error_ns) or max_abs_error_ns <= 0:
            raise AnalysisError("max_abs_error_ns must be positive and finite")
        if 1e9 / sr > max_abs_error_ns / 4:
            result["quality_warnings"].append("Sample resolution is coarse relative to requested tolerance")
        if verified_inputs:
            within = bool(result["error"]["max_abs_ns"] <= max_abs_error_ns)
            no_missing = result["missing_target_pulses"] == 0 and result["unmatched_target_pulses"] == 0
            result["verdict"] = "PASS_WAVEFORM" if within and no_missing else "FAIL_WAVEFORM"
        else:
            result["verdict"] = "NOT_EVALUATED"
    return result


def measure_pwm(wave: Waveform, *, polarity: str = "rising") -> dict[str, Any]:
    rising = polarity == "rising"
    edges = digital_edges(wave.raw, wave.samples, rising=rising)
    if edges.size < 3:
        return {"valid": False, "message": "Too few complete cycles", "edges": int(edges.size)}
    periods = np.diff(edges).astype(float)
    median = float(np.median(periods))
    # Robust median avoids frequency distortion from sparse missing/extra edges.
    if median <= 0:
        raise AnalysisError("Non-positive period")
    return {"valid": True, "channel": wave.channel, "cycles": len(periods),
            "frequency_hz_median": wave.sample_rate_hz / median,
            "period_ns_median": median * 1e9 / wave.sample_rate_hz,
            "period_samples_min": int(np.min(periods)),
            "period_samples_max": int(np.max(periods)),
            "period_ns_jitter_rms": float(np.std(periods)) * 1e9 / wave.sample_rate_hz,
            "evidence_source": wave.source, "integrity": wave.integrity}


def preview_edges(wave: Waveform, *, polarity: str = "rising", limit: int = 50) -> dict[str, Any]:
    if not 1 <= limit <= 1000:
        raise AnalysisError("limit must be 1..1000")
    edges = digital_edges(wave.raw, wave.samples, rising=polarity == "rising")
    return {"channel": wave.channel, "edge_count": len(edges), "edges":
            [{"sample": int(s), "time_ns": float(s) * 1e9 / wave.sample_rate_hz}
             for s in edges[:limit]], "truncated": len(edges) > limit,
            "evidence_source": wave.source, "integrity": wave.integrity}


def digital_transitions(raw: bytes, sample_count: int,
                        *, max_edges: int = 2_000_000) -> tuple[np.ndarray, np.ndarray]:
    """All level changes as (sample_index, new_level) in chronological order."""
    rising = digital_edges(raw, sample_count, rising=True, max_edges=max_edges)
    falling = digital_edges(raw, sample_count, rising=False, max_edges=max_edges)
    idx = np.concatenate((rising, falling))
    lvl = np.concatenate((np.ones(rising.shape, dtype=np.uint8),
                          np.zeros(falling.shape, dtype=np.uint8)))
    order = np.argsort(idx, kind="stable")
    return idx[order], lvl[order]


def to_vcd(wave: Waveform, *, timescale_ns: int = 1, max_edges: int = 2_000_000) -> str:
    """Value Change Dump of one channel.

    Edge-based (only changes are written), so exports stay compact and bounded;
    the initial level is emitted at time 0. Timestamps are rounded to ns.
    """
    if wave.samples < 1:
        raise AnalysisError("Cannot export an empty waveform")
    if timescale_ns < 1:
        raise AnalysisError("timescale_ns must be positive")
    idx, lvl = digital_transitions(wave.raw, wave.samples, max_edges=max_edges)
    ns_per_sample = 1e9 / wave.sample_rate_hz
    lines = [
        f"$timescale {timescale_ns}ns $end",
        "$scope module dl16 $end",
        f"$var wire 1 ! ch{wave.channel} $end",
        "$upscope $end",
        "$enddefinitions $end",
        "#0",
        f"{int(wave.raw[0] & 1)}!",
    ]
    for sample, level in zip(idx, lvl):
        lines.append(f"#{int(round(int(sample) * ns_per_sample))}")
        lines.append(f"{int(level)}!")
    return "\n".join(lines) + "\n"


def to_edges_csv(wave: Waveform, *, polarity: str = "rising",
                 max_edges: int = 2_000_000) -> str:
    """CSV of rising (or falling) edge sample index, timestamp and level."""
    if polarity not in ("rising", "falling"):
        raise AnalysisError("polarity must be rising or falling")
    idx = digital_edges(wave.raw, wave.samples, rising=polarity == "rising", max_edges=max_edges)
    ns_per_sample = 1e9 / wave.sample_rate_hz
    level = 1 if polarity == "rising" else 0
    rows = ["sample,time_ns,level"]
    rows.extend(f"{int(s)},{int(round(int(s) * ns_per_sample))},{level}" for s in idx)
    return "\n".join(rows) + "\n"


def to_samples_csv(wave: Waveform, *, max_samples: int = 2_000_000) -> str:
    """CSV of every sample (sample,time_ns,level); bounded by max_samples."""
    if max_samples < 1:
        raise AnalysisError("max_samples must be positive")
    if wave.samples > max_samples:
        raise AnalysisError(f"Capture has {wave.samples} samples; exceeds sample export limit {max_samples}")
    bits = np.unpackbits(np.frombuffer(wave.raw, dtype=np.uint8),
                         bitorder="little")[:wave.samples]
    ns_per_sample = 1e9 / wave.sample_rate_hz
    rows = ["sample,time_ns,level"]
    rows.extend(f"{i},{int(round(i * ns_per_sample))},{int(bit)}" for i, bit in enumerate(bits))
    return "\n".join(rows) + "\n"


def glitch_filter(raw: bytes, sample_count: int, *, min_pulse_samples: int,
                  max_edges: int = 2_000_000) -> tuple[bytes, int]:
    """Return (filtered_bits, removed_pulse_count).

    Any run shorter than min_pulse_samples is replaced by the surrounding stable
    level (a leading short run takes the next run's level). Never drops samples.
    """
    if min_pulse_samples < 1:
        raise AnalysisError("min_pulse_samples must be positive")
    if sample_count < 0 or sample_count > len(raw) * 8:
        raise AnalysisError("Invalid sample count for packed waveform")
    if sample_count == 0:
        return b"", 0
    bits = np.unpackbits(np.frombuffer(raw, dtype=np.uint8), bitorder="little")[:sample_count]
    changes = np.flatnonzero(np.diff(bits.astype(np.int8)) != 0) + 1
    starts = np.concatenate(([0], changes))
    ends = np.concatenate((changes, [sample_count]))
    if len(starts) - 1 > max_edges:
        raise AnalysisError("Too many runs: narrow the analysis window")
    out = bits.copy()
    removed = 0
    last_stable: int | None = None
    for i, (s, e) in enumerate(zip(starts, ends)):
        if e - s >= min_pulse_samples:
            last_stable = int(bits[s])
        else:
            if last_stable is None:
                nxt = int(bits[starts[i + 1]]) if i + 1 < len(starts) else 0
                out[s:e] = nxt
            else:
                out[s:e] = last_stable
            removed += 1
    return np.packbits(out, bitorder="little").tobytes(), removed


def search_conditions(waves: dict[int, Waveform], conditions, *, limit: int = 100,
                      max_samples: int = 200_000_000) -> dict[str, Any]:
    """Sample indices where every (channel, kind) condition holds simultaneously.

    kind is rising / falling (edge index) or high / low (level at that sample).
    """
    if not conditions:
        raise AnalysisError("At least one condition is required")
    if not 1 <= limit <= 10_000:
        raise AnalysisError("limit must be 1..10000")
    counts = {ch: waves[ch].samples for ch, _ in conditions}
    if len(set(counts.values())) != 1:
        raise AnalysisError("All condition channels must share a sample count")
    n = next(iter(counts.values()))
    if n > max_samples:
        raise AnalysisError("Capture too large for in-memory search; narrow it first")
    if n == 0:
        return {"success": True, "total_matches": 0, "returned": 0, "matches": [], "truncated": False}
    rate = waves[conditions[0][0]].sample_rate_hz
    mask = np.ones(n, dtype=bool)
    for ch, kind in conditions:
        w = waves[ch]
        if kind in ("high", "low"):
            bits = np.unpackbits(np.frombuffer(w.raw, dtype=np.uint8),
                                 bitorder="little")[:n].astype(bool)
            m = bits if kind == "high" else ~bits
        elif kind in ("rising", "falling"):
            idx = digital_edges(w.raw, n, rising=kind == "rising")
            m = np.zeros(n, dtype=bool)
            m[idx[idx < n]] = True
        else:
            raise AnalysisError("Condition kind must be rising/falling/high/low")
        mask &= m
    total = int(mask.sum())
    hits = np.flatnonzero(mask)[:limit]
    return {"success": True, "total_matches": total, "returned": int(hits.size),
            "matches": [{"sample": int(s), "time_ns": float(s) * 1e9 / rate} for s in hits],
            "truncated": total > int(hits.size)}
