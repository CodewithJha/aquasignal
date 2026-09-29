"""Typed, deterministically serializable detector parameter objects."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal, Mapping

from app.domain.signal.value_objects import TimeWindow
from app.signals.ordinals import TEMPORAL_ORDINAL_FIELDS


def _iso(dt: datetime) -> str:
    return dt.isoformat()


@dataclass(frozen=True, slots=True)
class TemporalBaselineParams:
    """Parameters for ``temporal_baseline_shift`` v1.

    Windows are absolute half-open ``[start, end)`` intervals (same as TimeWindow).
    """

    field_code: str
    baseline_window: TimeWindow
    recent_window: TimeWindow
    minimum_baseline_samples: int = 5
    minimum_recent_samples: int = 3
    threshold_multiplier: float = 3.0
    scale: Literal["mad", "iqr"] = "mad"

    def __post_init__(self) -> None:
        if self.field_code not in TEMPORAL_ORDINAL_FIELDS:
            raise ValueError(
                f"field_code {self.field_code!r} has no ordinal map; "
                f"allowed: {sorted(TEMPORAL_ORDINAL_FIELDS)}"
            )
        if self.minimum_baseline_samples < 1 or self.minimum_recent_samples < 1:
            raise ValueError("minimum sample counts must be >= 1")
        if self.threshold_multiplier < 0:
            raise ValueError("threshold_multiplier must be >= 0")
        if self.scale not in ("mad", "iqr"):
            raise ValueError("scale must be 'mad' or 'iqr'")

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline_window": {
                "end": _iso(self.baseline_window.end),
                "start": _iso(self.baseline_window.start),
            },
            "field_code": self.field_code,
            "minimum_baseline_samples": self.minimum_baseline_samples,
            "minimum_recent_samples": self.minimum_recent_samples,
            "recent_window": {
                "end": _iso(self.recent_window.end),
                "start": _iso(self.recent_window.start),
            },
            "scale": self.scale,
            "threshold_multiplier": self.threshold_multiplier,
        }

    def to_canonical_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> TemporalBaselineParams:
        bw = raw["baseline_window"]
        rw = raw["recent_window"]
        return cls(
            field_code=str(raw["field_code"]),
            baseline_window=TimeWindow(
                start=_parse_dt(bw["start"]),
                end=_parse_dt(bw["end"]),
            ),
            recent_window=TimeWindow(
                start=_parse_dt(rw["start"]),
                end=_parse_dt(rw["end"]),
            ),
            minimum_baseline_samples=int(raw.get("minimum_baseline_samples", 5)),
            minimum_recent_samples=int(raw.get("minimum_recent_samples", 3)),
            threshold_multiplier=float(raw.get("threshold_multiplier", 3.0)),
            scale=raw.get("scale", "mad"),  # type: ignore[arg-type]
        )


DEFAULT_CONTRADICTION_WINDOW = timedelta(hours=24)
DEFAULT_DUPLICATE_MAX_DELTA = timedelta(minutes=10)


@dataclass(frozen=True, slots=True)
class ContradictionParams:
    """Parameters for ``cross_observation_contradiction`` v2.

    ``comparison_window`` is independent of the overall analysis window: only
    observation pairs with |Δt| <= comparison_window are compared at all.
    ``duplicate_max_delta`` must not exceed the comparison window.
    """

    field_codes: tuple[str, ...] = (
        "foam",
        "macrophytes",
        "riparian_vegetation",
        "hydromorphology",
        "colour",
        "smell",
    )
    # A pair identical on every shared field within this delta is one duplicate
    # submission (double tap / re-upload), not independent corroboration.
    duplicate_max_delta: timedelta = DEFAULT_DUPLICATE_MAX_DELTA
    # Require at least this many evidence rows with a comparable field.
    minimum_comparable_observations: int = 2
    # Same-visit scope: observations further apart describe different visits.
    comparison_window: timedelta = DEFAULT_CONTRADICTION_WINDOW

    def __post_init__(self) -> None:
        if self.comparison_window < timedelta(0):
            raise ValueError("comparison_window must be >= 0")
        if self.duplicate_max_delta < timedelta(0):
            raise ValueError("duplicate_max_delta must be >= 0")
        if self.duplicate_max_delta > self.comparison_window:
            raise ValueError("duplicate_max_delta must not exceed comparison_window")

    def to_dict(self) -> dict[str, Any]:
        return {
            "comparison_window_seconds": self.comparison_window.total_seconds(),
            "duplicate_max_delta_seconds": self.duplicate_max_delta.total_seconds(),
            "field_codes": list(self.field_codes),
            "minimum_comparable_observations": self.minimum_comparable_observations,
        }

    def to_canonical_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> ContradictionParams:
        codes = raw.get("field_codes")
        delta_s = raw.get(
            "duplicate_max_delta_seconds", DEFAULT_DUPLICATE_MAX_DELTA.total_seconds()
        )
        window_s = raw.get(
            "comparison_window_seconds", DEFAULT_CONTRADICTION_WINDOW.total_seconds()
        )
        return cls(
            field_codes=tuple(codes) if codes is not None else cls().field_codes,
            duplicate_max_delta=timedelta(seconds=float(delta_s)),
            minimum_comparable_observations=int(
                raw.get("minimum_comparable_observations", 2)
            ),
            comparison_window=timedelta(seconds=float(window_s)),
        )


def _parse_dt(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)
