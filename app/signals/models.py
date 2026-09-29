"""Signal-engine analysis contracts — pure, serializable, no persistence IDs."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Mapping, Sequence

from app.domain.evidence.enums import EvidenceSourceClass, RelationType
from app.domain.signal.enums import SignalType
from app.domain.signal.value_objects import DetectorId, DetectorVersion, TimeWindow
from app.domain.value_objects import SiteRef


class DetectionStatus(str, Enum):
    """Outcome of one detector analysis — distinct from 'detector ran'."""

    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    NO_SIGNAL = "no_meaningful_shift"
    SIGNAL = "signal"


@dataclass(frozen=True, slots=True)
class EvidenceObservation:
    """Normalized evidence row for detectors (not a persistence entity).

    Field values are protocol-lite ConfirmGate vocabulary strings.
    Fixtures must set ``source_class=fixture`` and ``is_synthetic=True``.
    """

    evidence_id: str
    site: SiteRef
    observed_at: datetime
    source_class: EvidenceSourceClass
    is_synthetic: bool
    fields: Mapping[str, str]
    payload_ref: str = ""
    content_hash: str = ""
    license_tag: str = "fixture-owned-mit"

    def __post_init__(self) -> None:
        # Freeze fields as a plain dict for stable iteration elsewhere.
        object.__setattr__(self, "fields", dict(self.fields))

    def normalized_fields(self) -> dict[str, str]:
        """Lowercased stripped field map, sorted-key view for hashing helpers."""
        return {
            code: str(value).strip().lower()
            for code, value in sorted(self.fields.items(), key=lambda kv: kv[0])
        }


@dataclass(frozen=True, slots=True)
class AnalysisContext:
    """Immutable analysis scope. No repos, HTTP, AI, or DB handles."""

    site: SiteRef
    time_window: TimeWindow
    params: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "params", dict(self.params))

    def param(self, key: str, default: Any = None) -> Any:
        return self.params.get(key, default)


@dataclass(frozen=True, slots=True)
class RelationResult:
    """Canonical evidence↔evidence stance (left_ref < right_ref by evidence_id)."""

    relation_type: RelationType
    left_ref: str
    right_ref: str
    rationale_code: str
    message: str
    field_code: str
    value_left: str
    value_right: str
    observed_at_left: datetime
    observed_at_right: datetime
    comparison_rule: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "relation_type": self.relation_type.value,
            "left_ref": self.left_ref,
            "right_ref": self.right_ref,
            "rationale_code": self.rationale_code,
            "message": self.message,
            "field_code": self.field_code,
            "value_left": self.value_left,
            "value_right": self.value_right,
            "observed_at_left": self.observed_at_left.isoformat(),
            "observed_at_right": self.observed_at_right.isoformat(),
            "comparison_rule": self.comparison_rule,
        }


@dataclass(frozen=True, slots=True)
class SignalResult:
    """Structured detector output ready for A4 → EnvironmentalSignal mapping.

    Does **not** assign random signal_id / relation_id — application does that later.
    """

    status: DetectionStatus
    detector_id: DetectorId
    detector_version: DetectorVersion
    site: SiteRef
    time_window: TimeWindow
    summary: str
    metrics: Mapping[str, Any]
    evidence_ids: tuple[str, ...]
    explanation: Mapping[str, Any]
    signal_type: SignalType | None = None
    relations: tuple[RelationResult, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "metrics", dict(self.metrics))
        object.__setattr__(self, "explanation", dict(self.explanation))

    def to_canonical_dict(self) -> dict[str, Any]:
        """Deterministic JSON-serializable dict (sorted keys at dumps)."""
        return {
            "detector_id": self.detector_id.value,
            "detector_version": self.detector_version.value,
            "evidence_ids": list(self.evidence_ids),
            "explanation": _canonicalize(self.explanation),
            "metrics": _canonicalize(self.metrics),
            "relations": [r.to_dict() for r in self.relations],
            "signal_type": None if self.signal_type is None else self.signal_type.value,
            "site_id": self.site.site_id,
            "status": self.status.value,
            "summary": self.summary,
            "time_window": {
                "end": self.time_window.end.isoformat(),
                "start": self.time_window.start.isoformat(),
            },
        }

    def to_canonical_json(self) -> str:
        return json.dumps(
            self.to_canonical_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )


def _canonicalize(value: Any) -> Any:
    """Recursively normalize floats and dict key order for stable serialization."""
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):  # noqa: PLR0124
            raise ValueError("NaN/Inf must not appear in signal metrics")
        # Fixed decimal places for cross-platform float stability.
        return round(value, 10)
    if isinstance(value, Mapping):
        return {k: _canonicalize(value[k]) for k in sorted(value.keys())}
    if isinstance(value, (list, tuple)):
        return [_canonicalize(v) for v in value]
    return value


def sort_observations(
    evidence: Sequence[EvidenceObservation],
) -> list[EvidenceObservation]:
    """Deterministic order: observed_at ascending, then evidence_id ascending."""
    return sorted(evidence, key=lambda e: (e.observed_at, e.evidence_id))


def canonical_pair(
    a: EvidenceObservation, b: EvidenceObservation
) -> tuple[EvidenceObservation, EvidenceObservation]:
    """Order pair so left.evidence_id <= right.evidence_id."""
    if a.evidence_id <= b.evidence_id:
        return a, b
    return b, a
