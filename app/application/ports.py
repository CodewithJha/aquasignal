"""Narrow repository ports — intent methods, not execute_sql.

Infrastructure (SQLite today, Postgres later) implements these.
Domain and application never import sqlite3 / drivers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol, Sequence

from app.domain.evidence.item import EvidenceItem
from app.domain.evidence.relation import EvidenceRelation
from app.domain.evidence.snapshot import EvidenceSnapshot
from app.domain.investigation.analysis_run import AnalysisRun
from app.domain.investigation.case import InvestigationCase
from app.domain.investigation.decision import HumanDecision
from app.domain.packet import ObservationPacket
from app.domain.provenance_port import ProvenanceIntent
from app.domain.signal.environmental import EnvironmentalSignal


@dataclass(frozen=True, slots=True)
class PacketRecord:
    """Reconstructed aggregate plus optimistic-concurrency revision."""

    packet: ObservationPacket
    revision: int
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class CaseRecord:
    """InvestigationCase plus optimistic-concurrency version (persistence layer)."""

    case: InvestigationCase
    version: int


@dataclass(frozen=True, slots=True)
class ReviewQueueItem:
    """Narrow worklist row for NEEDS_REVIEW desk — not a BI dashboard KPI.

    Ordering policy (documented): oldest first by ``created_at`` ascending,
    tie-break ``packet_id`` ascending. Flag counts/severity are snapshot
    summaries for triage, never a composite trust score.
    """

    packet_id: str
    site_ref_id: str
    site_label: str
    city: str
    workflow_state: str
    revision: int
    created_at: datetime | None
    effective_at: datetime | None
    flag_count: int
    max_severity: str | None
    review_reason: str
    hard_count: int = 0
    soft_count: int = 0
    warn_count: int = 0


@dataclass(frozen=True, slots=True)
class ProvenanceRecord:
    """Durable append-only provenance row (ordered by seq)."""

    event_id: str
    packet_id: str
    seq: int
    at: datetime
    actor_type: str
    actor_id: str
    action: str
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    model_id: str | None = None
    prompt_version: str | None = None
    rule_engine_version: str | None = None

    def to_audit_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "packet_id": self.packet_id,
            "seq": self.seq,
            "at": self.at.isoformat(),
            "actor_type": self.actor_type,
            "actor_id": self.actor_id,
            "action": self.action,
            "before": self.before,
            "after": self.after,
            "model_id": self.model_id,
            "prompt_version": self.prompt_version,
            "rule_engine_version": self.rule_engine_version,
        }


class ObservationPacketRepository(Protocol):
    def get(self, packet_id: str) -> PacketRecord | None:
        ...

    def exists(self, packet_id: str) -> bool:
        ...

    def save(self, packet: ObservationPacket, *, expected_revision: int) -> PacketRecord:
        """Insert (expected_revision==0) or update with optimistic concurrency.

        Returns the stored record with the new revision.
        Raises DuplicatePacket, ConcurrencyConflict, PacketNotFound, PersistenceFailure.
        """
        ...

    def list_ids_for_site(self, site_ref_id: str, *, exclude_packet_id: str | None = None) -> list[str]:
        """Identity helpers for duplicate lookup — opaque ids only."""
        ...

    def list_finalized_ids_for_site(self, site_ref_id: str) -> list[str]:
        """FINALIZED packet ids for one site (AquaSignal evidence candidates)."""
        ...

    def list_for_review(
        self,
        *,
        states: Sequence[str] = ("NEEDS_REVIEW",),
        limit: int = 100,
    ) -> list[ReviewQueueItem]:
        """Narrow worklist: filter by workflow_state, oldest-first ordering.

        Not a generic query builder. Default states = NEEDS_REVIEW only.
        """
        ...


class ProvenanceRepository(Protocol):
    """Append-only. No update/delete API by design."""

    def append(self, intent: ProvenanceIntent) -> ProvenanceRecord:
        ...

    def append_many(self, intents: Sequence[ProvenanceIntent]) -> list[ProvenanceRecord]:
        ...

    def list_for_packet(self, packet_id: str) -> list[ProvenanceRecord]:
        ...


class EvidenceItemRepository(Protocol):
    def get(self, evidence_id: str) -> EvidenceItem | None: ...
    def require(self, evidence_id: str) -> EvidenceItem: ...
    def save(self, item: EvidenceItem) -> EvidenceItem: ...


class EvidenceSnapshotRepository(Protocol):
    def get(self, snapshot_id: str) -> EvidenceSnapshot | None: ...
    def require(self, snapshot_id: str) -> EvidenceSnapshot: ...
    def save(self, snapshot: EvidenceSnapshot) -> EvidenceSnapshot: ...
    def find_for_hash(
        self, snapshot_hash: str, *, near: datetime | None = None
    ) -> EvidenceSnapshot | None: ...


class EvidenceRelationRepository(Protocol):
    def get(self, relation_id: str) -> EvidenceRelation | None: ...
    def require(self, relation_id: str) -> EvidenceRelation: ...
    def save(self, relation: EvidenceRelation) -> EvidenceRelation: ...
    def list_for_run(self, analysis_run_id: str) -> list[EvidenceRelation]: ...


class EnvironmentalSignalRepository(Protocol):
    def get(self, signal_id: str) -> EnvironmentalSignal | None: ...
    def require(self, signal_id: str) -> EnvironmentalSignal: ...
    def save(self, signal: EnvironmentalSignal) -> EnvironmentalSignal: ...
    def list_for_run(self, analysis_run_id: str) -> list[EnvironmentalSignal]: ...


class AnalysisRunRepository(Protocol):
    def get(self, run_id: str) -> AnalysisRun | None: ...
    def require(self, run_id: str) -> AnalysisRun: ...
    def save(self, run: AnalysisRun) -> AnalysisRun: ...
    def list_for_snapshot_hash(self, snapshot_hash: str) -> list[AnalysisRun]: ...
    def list_for_site(self, site_id: str) -> list[AnalysisRun]: ...


class InvestigationCaseRepository(Protocol):
    def get(self, case_id: str) -> CaseRecord | None: ...
    def require(self, case_id: str) -> CaseRecord: ...
    def save(self, case: InvestigationCase, *, expected_version: int) -> CaseRecord: ...
    def list_for_site(self, site_id: str) -> list[CaseRecord]: ...
    def find_active_for_run(self, analysis_run_id: str) -> CaseRecord | None: ...


class HumanDecisionRepository(Protocol):
    def get(self, decision_id: str) -> HumanDecision | None: ...
    def require(self, decision_id: str) -> HumanDecision: ...
    def save(self, decision: HumanDecision) -> HumanDecision: ...
    def list_for_case(self, case_id: str) -> list[HumanDecision]: ...


class UnitOfWork(Protocol):
    """Atomic boundary for ConfirmGate + AquaSignal repos (shared connection)."""

    packets: ObservationPacketRepository
    provenance: ProvenanceRepository
    evidence_items: EvidenceItemRepository
    evidence_snapshots: EvidenceSnapshotRepository
    evidence_relations: EvidenceRelationRepository
    environmental_signals: EnvironmentalSignalRepository
    analysis_runs: AnalysisRunRepository
    investigation_cases: InvestigationCaseRepository
    human_decisions: HumanDecisionRepository

    def __enter__(self) -> UnitOfWork:
        ...

    def __exit__(self, exc_type, exc, tb) -> None:
        ...

    def commit(self) -> None:
        ...

    def rollback(self) -> None:
        ...
