"""Deterministic analysis-parameter hashing for AnalysisRun.parameters_hash."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


def canonicalize_params(value: Any) -> Any:
    """Recursively normalize params for stable SHA-256 (no secrets)."""
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):  # noqa: PLR0124
            raise ValueError("NaN/Inf must not appear in analysis parameters")
        return round(value, 10)
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return canonicalize_params(value.to_dict())
    if isinstance(value, Mapping):
        return {str(k): canonicalize_params(value[k]) for k in sorted(value.keys(), key=str)}
    if isinstance(value, (list, tuple)):
        return [canonicalize_params(v) for v in value]
    if hasattr(value, "isoformat") and callable(value.isoformat):
        return value.isoformat()
    if hasattr(value, "value"):
        # Enum-like
        return canonicalize_params(value.value)
    raise TypeError(f"cannot canonicalize analysis param type {type(value)!r}")


def hash_analysis_parameters(params: Mapping[str, Any] | None) -> str:
    """SHA-256 over canonical JSON of analysis params (empty dict if None)."""
    payload = canonicalize_params(dict(params or {}))
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
