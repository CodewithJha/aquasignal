"""SignalDetector protocol — deterministic, side-effect-free analysis."""

from __future__ import annotations

from typing import Protocol, Sequence, runtime_checkable

from app.domain.signal.value_objects import DetectorId, DetectorVersion
from app.signals.models import AnalysisContext, EvidenceObservation, SignalResult


@runtime_checkable
class SignalDetector(Protocol):
    """Pure detector: same evidence+context+version → same SignalResults."""

    @property
    def detector_id(self) -> DetectorId: ...

    @property
    def detector_version(self) -> DetectorVersion: ...

    def analyze(
        self,
        evidence: Sequence[EvidenceObservation],
        context: AnalysisContext,
    ) -> Sequence[SignalResult]: ...
