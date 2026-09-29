"""AquaSignal signal domain: EnvironmentalSignal + related value objects."""

from app.domain.signal.enums import SignalType
from app.domain.signal.environmental import EnvironmentalSignal
from app.domain.signal.value_objects import (
    DetectorId,
    DetectorVersion,
    EvidenceSnapshotRef,
    TimeWindow,
)

__all__ = [
    "SignalType",
    "EnvironmentalSignal",
    "DetectorId",
    "DetectorVersion",
    "EvidenceSnapshotRef",
    "TimeWindow",
]
