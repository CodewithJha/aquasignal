"""Map pure SignalResult → domain EnvironmentalSignal + EvidenceRelation."""

from __future__ import annotations

from typing import Sequence
from uuid import uuid4

from app.domain.evidence.relation import EvidenceRelation
from app.domain.signal.environmental import EnvironmentalSignal
from app.signals.models import DetectionStatus, SignalResult


def map_signal_results(
    results: Sequence[SignalResult],
    *,
    analysis_run_id: str,
) -> tuple[tuple[EnvironmentalSignal, ...], tuple[EvidenceRelation, ...]]:
    """Assign IDs; persist only results with a signal_type (not NO_SIGNAL).

    Relations from every result are mapped (including empty).
    """
    signals: list[EnvironmentalSignal] = []
    relations: list[EvidenceRelation] = []

    for result in results:
        signal_id: str | None = None
        if result.signal_type is not None:
            # INSUFFICIENT_EVIDENCE and SIGNAL both carry a typed hypothesis.
            signal_id = f"sig_{uuid4().hex[:12]}"
            signals.append(
                EnvironmentalSignal.create(
                    signal_id=signal_id,
                    detector_id=result.detector_id,
                    detector_version=result.detector_version,
                    signal_type=result.signal_type,
                    site=result.site,
                    time_window=result.time_window,
                    summary=result.summary,
                    metrics=result.metrics,
                    evidence_ids=result.evidence_ids,
                    analysis_run_id=analysis_run_id,
                    explanation={
                        **dict(result.explanation),
                        "detection_status": result.status.value,
                    },
                )
            )
        elif result.status is DetectionStatus.NO_SIGNAL:
            # Explicit no-op: no durable EnvironmentalSignal for no_meaningful_shift.
            pass

        for rel in result.relations:
            relations.append(
                EvidenceRelation.create(
                    relation_id=f"rel_{uuid4().hex[:12]}",
                    relation_type=rel.relation_type,
                    left_ref=rel.left_ref,
                    right_ref=rel.right_ref,
                    analysis_run_id=analysis_run_id,
                    rationale_code=rel.rationale_code,
                    message=rel.message,
                )
            )

    return tuple(signals), tuple(relations)
