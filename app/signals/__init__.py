"""AquaSignal deterministic Signal Engine (Phase A3).

Pure analysis: EvidenceObservation → SignalDetector → SignalResult.
No persistence, UI, AI, FHIR, or ConfirmGate workflow gates.
"""

from app.signals.engine import SignalEngine
from app.signals.models import (
    AnalysisContext,
    DetectionStatus,
    EvidenceObservation,
    RelationResult,
    SignalResult,
)
from app.signals.registry import (
    DETECTOR_SET_VERSION,
    SignalDetectorRegistry,
    default_registry,
)

__all__ = [
    "AnalysisContext",
    "DETECTOR_SET_VERSION",
    "DetectionStatus",
    "EvidenceObservation",
    "RelationResult",
    "SignalDetectorRegistry",
    "SignalEngine",
    "SignalResult",
    "default_registry",
]
