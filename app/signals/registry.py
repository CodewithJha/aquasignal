"""Fixed, deterministic detector registry — no plugin discovery."""

from __future__ import annotations

from typing import Sequence

from app.signals.detectors.cross_observation_contradiction import (
    CrossObservationContradictionDetector,
)
from app.signals.detectors.temporal_baseline_shift import TemporalBaselineShiftDetector
from app.signals.protocol import SignalDetector

# Explicit set identity for AnalysisRun.detector_set_version (A4).
DETECTOR_SET_VERSION = "aquasignal-detectors-a3-v2"

class SignalDetectorRegistry:
    """Returns configured detector instances in deterministic order."""

    def __init__(self, detectors: Sequence[SignalDetector] | None = None) -> None:
        if detectors is None:
            # Fixed order: temporal, then contradiction. Never filesystem order.
            self._detectors: tuple[SignalDetector, ...] = (
                TemporalBaselineShiftDetector(),
                CrossObservationContradictionDetector(),
            )
        else:
            self._detectors = tuple(detectors)

    @property
    def version(self) -> str:
        return DETECTOR_SET_VERSION

    def detectors(self) -> tuple[SignalDetector, ...]:
        return self._detectors

    def descriptors(self) -> tuple[str, ...]:
        """Stable ``detector_id:version`` strings in execution order."""
        return tuple(
            f"{d.detector_id.value}:{d.detector_version.value}" for d in self._detectors
        )


def default_registry() -> SignalDetectorRegistry:
    return SignalDetectorRegistry()
