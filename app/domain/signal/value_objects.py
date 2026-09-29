"""AquaSignal value objects — TimeWindow, detector identity, snapshot refs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.domain.errors import DomainValidationError


@dataclass(frozen=True, slots=True)
class TimeWindow:
    """Half-open interval ``[start, end)`` for cases and signals."""

    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.end <= self.start:
            raise DomainValidationError("TimeWindow requires end > start ([start, end))")

    def contains(self, instant: datetime) -> bool:
        return self.start <= instant < self.end


@dataclass(frozen=True, slots=True)
class DetectorId:
    """Opaque detector identity string (e.g. temporal_baseline_shift)."""

    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise DomainValidationError("DetectorId must be non-empty")


@dataclass(frozen=True, slots=True)
class DetectorVersion:
    """Semver-like detector version for reproducibility."""

    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise DomainValidationError("DetectorVersion must be non-empty")


@dataclass(frozen=True, slots=True)
class EvidenceSnapshotRef:
    """Pointer + content hash for a frozen evidence set."""

    snapshot_id: str
    snapshot_hash: str

    def __post_init__(self) -> None:
        if not self.snapshot_id.strip():
            raise DomainValidationError("snapshot_id is required")
        if not self.snapshot_hash.strip():
            raise DomainValidationError("snapshot_hash is required")
