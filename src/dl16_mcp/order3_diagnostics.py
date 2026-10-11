"""Offline, non-authoritative Order3 layout/range diagnostics.

This module preserves source bytes and never defines a crop rule or hardware
interpretation. Buffer byte-count semantics and Stream fields are mode-scoped.
"""
from __future__ import annotations

from typing import Any

SCHEMA = "dl16-order3-diagnostic/v1"
UINT40_MAX = (1 << 40) - 1
DEFAULT_MAX_CROP_BYTES = 32 * 1024 * 1024


def diagnose_order3(
    payload: bytes | bytearray | memoryview,
    *,
    mode: str,
    profile: str,
    request_depth_samples: int,
    max_crop_bytes: int = DEFAULT_MAX_CROP_BYTES,
) -> dict[str, Any]:
    """Describe a supported observed payload layout without interpreting it.

    Current layout hypothesis: 2-byte prefix, uint40 LE offset, sixteen uint40 LE
    channel fields, one-byte suffix (88 bytes total). Signed40 is included only
    as an explicitly untrusted alternative. Counts exceeding the caller's
    bounded budget are never exposed as usable crop/allocation inputs.
    """
    raw = bytes(payload)
    if len(raw) != 88:
        raise ValueError("Order3 layout v1 requires exactly 88 raw bytes")
    if mode not in ("BUFFER", "STREAM"):
        raise ValueError("mode must be BUFFER or STREAM")
    if not isinstance(profile, str) or not profile or len(profile) > 96:
        raise ValueError("profile must be a non-empty label of at most 96 characters")
    if isinstance(request_depth_samples, bool) or not isinstance(request_depth_samples, int) or request_depth_samples < 0:
        raise ValueError("request_depth_samples must be a non-negative integer")
    if isinstance(max_crop_bytes, bool) or not isinstance(max_crop_bytes, int) or not 0 <= max_crop_bytes <= DEFAULT_MAX_CROP_BYTES:
        raise ValueError("max_crop_bytes outside bounded diagnostic budget")

    offset = int.from_bytes(raw[2:7], "little", signed=False)
    fields = [int.from_bytes(raw[7 + 5 * i:12 + 5 * i], "little", signed=False) for i in range(16)]
    signed = [value - (1 << 40) if value & (1 << 39) else value for value in fields]
    plausible = [value if value <= max_crop_bytes else None for value in fields]
    if mode == "BUFFER":
        mode_status = "BUFFER_BYTE_COUNT_SOURCE_CONVENTION; diagnostics_do_not_crop"
    else:
        mode_status = "UNKNOWN_STREAM_UNITS; preserve_raw_no_crop"
    return {
        "schema": SCHEMA,
        "authority": "OFFLINE_LAYOUT_DIAGNOSTIC_NOT_PROTOCOL_INTERPRETATION",
        "mode": mode,
        "profile": profile,
        "request_depth_samples": request_depth_samples,
        "raw_hex": raw.hex(),
        "raw_length": len(raw),
        "layout_hypothesis": "prefix2_offset_u40le_count16_u40le_suffix1/v1",
        "prefix_hex": raw[:2].hex(),
        "offset_raw_u40": offset,
        "offset_signed40_hypothesis_not_interpretation": offset - (1 << 40) if offset & (1 << 39) else offset,
        "count_fields_raw_u40": fields,
        "count_fields_signed40_hypothesis_not_interpretation": signed,
        "count_fields_within_crop_budget_bytes_or_none": plausible,
        "count_field_status": ["OUT_OF_BUDGET_NOT_USABLE_AS_UNSIGNED_CROP_OR_ALLOCATION_INPUT" if v is None else "WITHIN_BUDGET_NOT_VALIDATED_AS_CROP" for v in plausible],
        "suffix_hex": raw[-1:].hex(),
        "mode_status": mode_status,
        "alignment_status": "UNKNOWN",
        "tail_status": "UNKNOWN",
        "valid_sample_count": None,
        "selected_crop": None,
    }
