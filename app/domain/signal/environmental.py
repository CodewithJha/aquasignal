"""EnvironmentalSignal — one detector hypothesis instance (not a diagnosis)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping
from uuid import uuid4

from app.domain.errors import DomainValidationError
from app.domain.signal.enums import SignalType
from app.domain.signal.value_objects import DetectorId, DetectorVersion, TimeWindow
from app.domain.value_objects import SiteRef


@dataclass(frozen=True, slots=True)
class EnvironmentalSignal:
    """Explainable detector output. Metrics are structured extras — not a trust score."""

    signal_id: str
    detector_id: DetectorId
    detector_version: DetectorVersion
    signal_type: SignalType
    site: SiteRef
    time_window: TimeWindow
    summary: str
    metrics: Mapping[str, Any]
    evidence_ids: tuple[str, ...]
    analysis_run_id: str
    explanation: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        detector_id: DetectorId,
        detector_version: DetectorVersion,
        signal_type: SignalType,
        site: SiteRef,
        time_window: TimeWindow,
        summary: str,
        metrics: Mapping[str, Any],
        evidence_ids: tuple[str, ...] | list[str],
        analysis_run_id: str,
        explanation: Mapping[str, Any] | None = None,
        signal_id: str | None = None,
    ) -> EnvironmentalSignal:
        if not summary.strip():
            raise DomainValidationError("summary is required (non-causal, human-readable)")
        if not analysis_run_id.strip():
            raise DomainValidationError("analysis_run_id is required")
        ids = tuple(evidence_ids)
        return cls(
            signal_id=signal_id or f"sig_{uuid4().hex[:12]}",
            detector_id=detector_id,
            detector_version=detector_version,
            signal_type=signal_type,
            site=site,
            time_window=time_window,
            summary=summary.strip(),
            metrics=dict(metrics),
            evidence_ids=ids,
            analysis_run_id=analysis_run_id.strip(),
            explanation=dict(explanation or {}),
        )
