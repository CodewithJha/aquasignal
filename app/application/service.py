"""Thin ObservationService — load → domain mutation → persist + provenance.

No HTML, HTTP, SQL, FHIR, or AI inside this module.
FlagEngine is injected at construction (Deterministic in production/demo).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from app.application.errors import ConcurrencyConflict, PacketNotFound
from app.application.ports import PacketRecord, ProvenanceRecord, ReviewQueueItem, UnitOfWork
from app.domain.enums import ActorType
from app.domain.packet import ObservationPacket
from app.domain.provenance_port import ProvenanceIntent
from app.domain.value_objects import Actor, QualityFlag, SiteRef
from app.flags.engine import FlagEngine, NullFlagEngine

T = TypeVar("T")


class ObservationService:
    """Coordinates aggregate mutations with durable packet + provenance txs."""

    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        *,
        flag_engine: FlagEngine | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        # NullFlagEngine is test/fallback only — composition root injects Deterministic.
        self._flag_engine: FlagEngine = flag_engine or NullFlagEngine()

    @property
    def flag_engine(self) -> FlagEngine:
        return self._flag_engine

    def apply_engine_flags(
        self,
        packet: ObservationPacket,
        *,
        actor: Actor | None = None,
    ) -> list[QualityFlag]:
        """Evaluate injected FlagEngine and attach results.

        Allowed while RECEIVED / FLAGGED / NEEDS_REVIEW (Phase 7 revalidate).
        Does not open a DB transaction — caller persists. Routes must not call
        FlagEngine directly.
        """
        system = actor or Actor(ActorType.SYSTEM, "flag-engine")
        flags = self._flag_engine.evaluate(packet)
        packet.apply_flags(
            flags,
            actor=system,
            rule_engine_version=self._flag_engine.version,
        )
        return flags

    def get(self, packet_id: str) -> PacketRecord:
        with self._uow_factory() as uow:
            record = uow.packets.get(packet_id)
            if record is None:
                raise PacketNotFound(packet_id)
            return record

    def exists(self, packet_id: str) -> bool:
        with self._uow_factory() as uow:
            return uow.packets.exists(packet_id)

    def list_for_review(
        self,
        *,
        states: tuple[str, ...] = ("NEEDS_REVIEW",),
        limit: int = 100,
    ) -> list[ReviewQueueItem]:
        with self._uow_factory() as uow:
            return uow.packets.list_for_review(states=states, limit=limit)

    def create(
        self,
        site: SiteRef,
        *,
        packet_id: str | None = None,
        submitter_display: str | None = None,
        author_actor_id: str = "anonymous",
        effective_at=None,
    ) -> PacketRecord:
        packet = ObservationPacket.create(
            site,
            packet_id=packet_id,
            submitter_display=submitter_display,
            author_actor_id=author_actor_id,
            effective_at=effective_at,
        )
        return self.persist_new(packet)

    def persist_new(self, packet: ObservationPacket) -> PacketRecord:
        """Insert a newly created packet (revision 0 → 1) + drain intents."""
        return self._persist(packet, expected_revision=0)

    def persist(self, packet: ObservationPacket, *, expected_revision: int) -> PacketRecord:
        """Update an existing packet under optimistic concurrency + drain intents."""
        if expected_revision < 1:
            raise ValueError("expected_revision for update must be >= 1")
        return self._persist(packet, expected_revision=expected_revision)

    def mutate(
        self,
        packet_id: str,
        mutator: Callable[[ObservationPacket], T],
    ) -> tuple[PacketRecord, T]:
        """Load → apply mutator → save packet + provenance in one transaction."""
        with self._uow_factory() as uow:
            record = uow.packets.get(packet_id)
            if record is None:
                raise PacketNotFound(packet_id)
            result = mutator(record.packet)
            intents = record.packet.drain_provenance_intents()
            saved = uow.packets.save(record.packet, expected_revision=record.revision)
            if intents:
                uow.provenance.append_many(intents)
            uow.commit()
            return saved, result

    def mutate_at_revision(
        self,
        packet_id: str,
        expected_revision: int,
        mutator: Callable[[ObservationPacket], T],
    ) -> tuple[PacketRecord, T]:
        """Like mutate, but refuse before domain work if revision does not match."""
        with self._uow_factory() as uow:
            record = uow.packets.get(packet_id)
            if record is None:
                raise PacketNotFound(packet_id)
            if record.revision != expected_revision:
                raise ConcurrencyConflict(packet_id, expected_revision)
            result = mutator(record.packet)
            intents = record.packet.drain_provenance_intents()
            saved = uow.packets.save(record.packet, expected_revision=record.revision)
            if intents:
                uow.provenance.append_many(intents)
            uow.commit()
            return saved, result

    def list_provenance(self, packet_id: str) -> list[ProvenanceRecord]:
        with self._uow_factory() as uow:
            if not uow.packets.exists(packet_id):
                raise PacketNotFound(packet_id)
            return uow.provenance.list_for_packet(packet_id)

    def append_provenance(self, intent: ProvenanceIntent) -> ProvenanceRecord:
        """Append one provenance event (must reference an existing packet)."""
        with self._uow_factory() as uow:
            if not uow.packets.exists(intent.packet_id):
                raise PacketNotFound(intent.packet_id)
            stored = uow.provenance.append(intent)
            uow.commit()
            return stored

    def _persist(
        self, packet: ObservationPacket, *, expected_revision: int
    ) -> PacketRecord:
        with self._uow_factory() as uow:
            intents = packet.drain_provenance_intents()
            saved = uow.packets.save(packet, expected_revision=expected_revision)
            if intents:
                uow.provenance.append_many(intents)
            uow.commit()
            return saved
