"""Robust statistics helpers for temporal_baseline_shift (no NaN/Inf)."""

from __future__ import annotations

from statistics import median
from typing import Sequence


def safe_median(values: Sequence[float]) -> float:
    if not values:
        raise ValueError("median of empty sequence")
    return float(median(values))


def median_absolute_deviation(values: Sequence[float], center: float | None = None) -> float:
    """Raw MAD = median(|x_i - median|). Not the 1.4826-scaled estimator."""
    if not values:
        raise ValueError("MAD of empty sequence")
    c = safe_median(values) if center is None else center
    return safe_median([abs(v - c) for v in values])


def interquartile_range(values: Sequence[float]) -> float:
    """IQR = Q3 - Q1 via nearest-rank on sorted sample (deterministic)."""
    if len(values) < 2:
        raise ValueError("IQR requires at least 2 values")
    ordered = sorted(values)
    n = len(ordered)
    # Exclusive median split for even n; include median in both for odd n.
    if n % 2 == 0:
        lower = ordered[: n // 2]
        upper = ordered[n // 2 :]
    else:
        mid = n // 2
        lower = ordered[:mid]
        upper = ordered[mid + 1 :]
    if not lower or not upper:
        return 0.0
    q1 = safe_median(lower)
    q3 = safe_median(upper)
    return float(q3 - q1)


def finite_float(value: float) -> float:
    """Reject NaN/Inf; round for stable serialization."""
    if value != value or value in (float("inf"), float("-inf")):  # noqa: PLR0124
        raise ValueError("non-finite float")
    return round(float(value), 10)
