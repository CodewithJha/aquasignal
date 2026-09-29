"""SignalEngine — deterministic orchestration of registered detectors."""

from __future__ import annotations

from typing import Sequence

from app.signals.models import AnalysisContext, EvidenceObservation, SignalResult
from app.signals.protocol import SignalDetector
from app.signals.registry import SignalDetectorRegistry, default_registry


class SignalEngine:
    """Run detectors in fixed registry order; concatenate results.

    Pure w.r.t. inputs: no I/O, no mutation of evidence, no persistence.
    """

    def __init__(
        self,
        detectors: Sequence[SignalDetector] | None = None,
        *,
        registry: SignalDetectorRegistry | None = None,
    ) -> None:
        if detectors is not None:
            self._detectors = tuple(detectors)
            self._registry_version = "custom"
        else:
            reg = registry or default_registry()
            self._detectors = reg.detectors()
            self._registry_version = reg.version

    @property
    def detector_set_version(self) -> str:
        return self._registry_version

    @property
    def detectors(self) -> tuple[SignalDetector, ...]:
        return self._detectors

    def analyze(
        self,
        evidence: Sequence[EvidenceObservation],
        context: AnalysisContext,
    ) -> tuple[SignalResult, ...]:
        # Defensive copy of the sequence order only; items are frozen.
        snapshot = tuple(evidence)
        results: list[SignalResult] = []
        for detector in self._detectors:
            results.extend(detector.analyze(snapshot, context))
        return tuple(results)
