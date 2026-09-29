"""EvidenceSnapshot — frozen, hashed input set for an AnalysisRun."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping
from uuid import uuid4

from app.domain.errors import DomainValidationError
from app.domain.signal.value_objects import EvidenceSnapshotRef


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def compute_snapshot_hash(
    ordered_evidence_ids: tuple[str, ...],
    source_manifest: Mapping[str, Any],
) -> str:
    """Deterministic SHA-256 over ordered ids + canonical manifest."""
    payload = {
        "evidence_ids": list(ordered_evidence_ids),
        "source_manifest": dict(sorted(source_manifest.items(), key=lambda kv: kv[0])),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class EvidenceSnapshot:
    """Frozen evidence set. Hash is independent of creation timestamp."""

    snapshot_id: str
    snapshot_hash: str
    created_at: datetime
    ordered_evidence_ids: tuple[str, ...]
    source_manifest: Mapping[str, Any]

    @classmethod
    def create(
        cls,
        *,
        ordered_evidence_ids: tuple[str, ...] | list[str],
        source_manifest: Mapping[str, Any] | None = None,
        created_at: datetime | None = None,
        snapshot_id: str | None = None,
    ) -> EvidenceSnapshot:
        ids = tuple(ordered_evidence_ids)
        if any(not eid.strip() for eid in ids):
            raise DomainValidationError("evidence ids must be non-empty")
        manifest = dict(source_manifest or {})
        digest = compute_snapshot_hash(ids, manifest)
        return cls(
            snapshot_id=snapshot_id or f"snap_{uuid4().hex[:12]}",
            snapshot_hash=digest,
            created_at=created_at or _utc_now(),
            ordered_evidence_ids=ids,
            source_manifest=manifest,
        )

    def as_ref(self) -> EvidenceSnapshotRef:
        return EvidenceSnapshotRef(
            snapshot_id=self.snapshot_id,
            snapshot_hash=self.snapshot_hash,
        )
