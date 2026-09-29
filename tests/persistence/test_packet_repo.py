"""Packet repository + serialization + concurrency + recovery tests."""

from __future__ import annotations


import pytest

from app.application.errors import (
    ConcurrencyConflict,
    DuplicatePacket,
    PacketNotFound,
)
from app.application.serialization import (
    dumps_document,
    loads_document,
    packet_to_document,
    document_to_packet,
)
from app.application.service import ObservationService
from app.domain.enums import Severity, WorkflowState
from app.domain.packet import ObservationPacket, make_flag
from app.domain.value_objects import Actor, FieldValue, SiteRef
from app.persistence.config import DatabaseSettings
from app.persistence.factory import open_unit_of_work
from tests.persistence.conftest import foam


def test_persist_reload_roundtrip(
    service: ObservationService,
    fresh_packet: ObservationPacket,
    citizen: Actor,
    system: Actor,
) -> None:
    packet = fresh_packet
    packet.set_field(foam(), actor=citizen)
    packet.apply_flags(
        [
            make_flag(
                rule_id="completeness.missing",
                severity=Severity.WARN,
                code="MISSING",
                message="advisory",
            )
        ],
        actor=system,
        rule_engine_version="0.1.0",
    )
    saved = service.persist_new(packet)
    assert saved.revision == 1
    assert saved.packet.packet_id == packet.packet_id

    loaded = service.get(packet.packet_id)
    assert loaded.revision == 1
    assert loaded.packet.workflow_state == WorkflowState.FLAGGED
    assert loaded.packet.fields["foam"].value == "present"
    assert loaded.packet.fields["foam"].source.value == "human"
    assert len(loaded.packet.flags) == 1
    assert loaded.packet.rule_engine_version == "0.1.0"
    assert loaded.packet.author_actor_id == citizen.actor_id


def test_not_found(service: ObservationService) -> None:
    with pytest.raises(PacketNotFound):
        service.get("does-not-exist")


def test_duplicate_insert(
    service: ObservationService, fresh_packet: ObservationPacket
) -> None:
    service.persist_new(fresh_packet)
    # Same id, fresh create path with expected_revision 0 again
    clone = ObservationPacket.rehydrate(
        packet_id=fresh_packet.packet_id,
        site=fresh_packet.site,
        workflow_state=WorkflowState.RECEIVED,
        author_actor_id=fresh_packet.author_actor_id,
    )
    with pytest.raises(DuplicatePacket):
        service.persist_new(clone)


def test_optimistic_concurrency_conflict(
    service: ObservationService,
    fresh_packet: ObservationPacket,
    citizen: Actor,
) -> None:
    service.persist_new(fresh_packet)
    a = service.get(fresh_packet.packet_id)
    b = service.get(fresh_packet.packet_id)
    a.packet.set_notes("from-a", actor=citizen)
    service.persist(a.packet, expected_revision=a.revision)
    b.packet.set_notes("from-b", actor=citizen)
    with pytest.raises(ConcurrencyConflict):
        service.persist(b.packet, expected_revision=b.revision)


def test_deterministic_serialization(fresh_packet: ObservationPacket, citizen: Actor) -> None:
    fresh_packet.set_field(FieldValue(code="colour", value="clear"), actor=citizen)
    fresh_packet.set_field(FieldValue(code="foam", value="absent"), actor=citizen)
    doc = packet_to_document(fresh_packet)
    text1 = dumps_document(doc)
    text2 = dumps_document(loads_document(text1))
    assert text1 == text2
    rebuilt = document_to_packet(loads_document(text1))
    assert rebuilt.packet_id == fresh_packet.packet_id
    assert set(rebuilt.fields) == {"colour", "foam"}
    assert rebuilt.pending_provenance() == ()


def test_restart_recovery_simulation(
    settings: DatabaseSettings,
    coimbra: SiteRef,
    citizen: Actor,
) -> None:
    conn1, factory1 = open_unit_of_work(settings)
    svc1 = ObservationService(factory1)
    packet = ObservationPacket.create(coimbra, author_actor_id=citizen.actor_id)
    packet.set_field(foam(), actor=citizen)
    svc1.persist_new(packet)
    packet_id = packet.packet_id
    conn1.close()

    # Destroy in-memory handles; open fresh connection to same file.
    conn2, factory2 = open_unit_of_work(settings)
    svc2 = ObservationService(factory2)
    loaded = svc2.get(packet_id)
    assert loaded.packet.fields["foam"].value == "present"
    events = svc2.list_provenance(packet_id)
    assert any(e.action == "packet.created" for e in events)
    assert any(e.action == "fields.set" for e in events)
    conn2.close()


def test_opaque_packet_ids_not_sequential(
    service: ObservationService, coimbra: SiteRef
) -> None:
    a = service.create(coimbra, author_actor_id="c1")
    b = service.create(coimbra, author_actor_id="c2")
    assert a.packet.packet_id != b.packet.packet_id
    assert not a.packet.packet_id.isdigit()
    assert len(a.packet.packet_id) >= 16


def test_exists(service: ObservationService, fresh_packet: ObservationPacket) -> None:
    assert service.exists(fresh_packet.packet_id) is False
    service.persist_new(fresh_packet)
    assert service.exists(fresh_packet.packet_id) is True
