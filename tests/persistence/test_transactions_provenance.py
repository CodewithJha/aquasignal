"""Transaction commit/rollback and provenance durability tests."""

from __future__ import annotations

from typing import Sequence

import pytest

from app.application.errors import ProvenanceAppendFailure
from app.application.ports import ProvenanceRecord
from app.application.service import ObservationService
from app.application.audit import answer_hitl_audit_questions
from app.domain.enums import ActorType, WorkflowState
from app.domain.packet import ObservationPacket
from app.domain.provenance_port import ProvenanceIntent
from app.domain.value_objects import Actor
from app.persistence.unit_of_work import SqliteUnitOfWork
from tests.persistence.conftest import foam


class _BoomProvenance:
    """Wraps real provenance repo and fails on append_many."""

    def __init__(self, inner) -> None:
        self._inner = inner

    def append(self, intent: ProvenanceIntent) -> ProvenanceRecord:
        raise ProvenanceAppendFailure("boom")

    def append_many(self, intents: Sequence[ProvenanceIntent]) -> list[ProvenanceRecord]:
        raise ProvenanceAppendFailure("boom")

    def list_for_packet(self, packet_id: str) -> list[ProvenanceRecord]:
        return self._inner.list_for_packet(packet_id)


def test_transaction_commits_packet_and_provenance(
    service: ObservationService,
    fresh_packet: ObservationPacket,
    citizen: Actor,
) -> None:
    fresh_packet.set_field(foam(), actor=citizen)
    service.persist_new(fresh_packet)
    events = service.list_provenance(fresh_packet.packet_id)
    assert len(events) >= 2
    assert events[0].seq < events[1].seq
    assert all(e.packet_id == fresh_packet.packet_id for e in events)


def test_transaction_rolls_back_when_provenance_fails(
    uow_factory,
    fresh_packet: ObservationPacket,
    citizen: Actor,
) -> None:
    fresh_packet.set_field(foam(), actor=citizen)
    packet_id = fresh_packet.packet_id

    class FailingUow(SqliteUnitOfWork):
        def __enter__(self):
            uow = super().__enter__()
            uow.provenance = _BoomProvenance(uow.provenance)  # type: ignore[method-assign]
            return uow

    # Build a factory that returns failing UoW sharing same connection style.
    base = uow_factory()

    def failing_factory():
        # Reuse connection from a real UoW
        real = uow_factory()
        return FailingUow(real._conn)  # noqa: SLF001 — test seam

    # Ensure connection is the shared one from fixture
    _ = base
    svc = ObservationService(failing_factory)
    with pytest.raises(ProvenanceAppendFailure):
        svc.persist_new(fresh_packet)

    # Fresh real service on same factory should not see the packet
    ok = ObservationService(uow_factory)
    assert ok.exists(packet_id) is False


def test_provenance_order_actor_and_immutability_api(
    service: ObservationService,
    fresh_packet: ObservationPacket,
    citizen: Actor,
    system: Actor,
) -> None:
    fresh_packet.set_field(foam(), actor=citizen)
    fresh_packet.apply_suggestions(
        {"foam": "absent"},
        actor=Actor(ActorType.AI_PROVIDER, "null"),
        model_id="null",
        prompt_version="0",
    )
    fresh_packet.apply_flags([], actor=system, rule_engine_version="0.1.0")
    service.persist_new(fresh_packet)

    events = service.list_provenance(fresh_packet.packet_id)
    seqs = [e.seq for e in events]
    assert seqs == sorted(seqs)
    assert events[0].action == "packet.created"
    assert any(e.actor_type == "citizen" for e in events)
    assert any(e.model_id == "null" for e in events if e.action == "suggestions.applied")

    # Repository has no update/delete API
    from app.persistence.provenance_repository import SqliteProvenanceRepository

    assert not hasattr(SqliteProvenanceRepository, "update")
    assert not hasattr(SqliteProvenanceRepository, "delete")
    assert not hasattr(SqliteProvenanceRepository, "execute_sql")


def test_provenance_survives_restart(
    settings,
    coimbra,
    citizen: Actor,
) -> None:
    from app.persistence.factory import open_unit_of_work

    conn1, factory1 = open_unit_of_work(settings)
    svc1 = ObservationService(factory1)
    packet = ObservationPacket.create(coimbra, author_actor_id=citizen.actor_id)
    svc1.persist_new(packet)
    pid = packet.packet_id
    n1 = len(svc1.list_provenance(pid))
    conn1.close()

    conn2, factory2 = open_unit_of_work(settings)
    svc2 = ObservationService(factory2)
    events = svc2.list_provenance(pid)
    assert len(events) == n1
    assert events[0].action == "packet.created"
    conn2.close()


def test_hitl_audit_answers_shape(
    service: ObservationService,
    fresh_packet: ObservationPacket,
    citizen: Actor,
    system: Actor,
) -> None:
    from tests.domain.conftest import reach_confirmed

    reach_confirmed(fresh_packet, system=system, citizen=citizen)
    fresh_packet.finalize(actor=system, one_health_sentence="cited")
    service.persist_new(fresh_packet)
    answers = answer_hitl_audit_questions(service.list_provenance(fresh_packet.packet_id))
    assert answers["5_who_confirmed_when"] != "N/A"
    assert answers["2_ai_suggestions"] == "N/A"
    assert "rule_engine_version" in answers["7_rule_and_mapper_versions"]


def test_mutate_persists_in_one_tx(
    service: ObservationService,
    fresh_packet: ObservationPacket,
    citizen: Actor,
) -> None:
    service.persist_new(fresh_packet)

    def add_field(p: ObservationPacket) -> None:
        p.set_field(foam(), actor=citizen)

    record, _ = service.mutate(fresh_packet.packet_id, add_field)
    assert record.revision == 2
    assert record.packet.workflow_state == WorkflowState.RECEIVED
    loaded = service.get(fresh_packet.packet_id)
    assert "foam" in loaded.packet.fields
