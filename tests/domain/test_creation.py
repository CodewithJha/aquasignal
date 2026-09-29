"""Creation, SiteRef cities, field allowlist."""

from __future__ import annotations

import pytest

from app.domain.cities import OAH_CITIES
from app.domain.enums import WorkflowState
from app.domain.errors import DomainValidationError, InvalidFieldValue
from app.domain.packet import ObservationPacket
from app.domain.value_objects import Actor, FieldValue, SiteRef


def test_oah_cities_exactly_five() -> None:
    assert OAH_CITIES == frozenset(
        {"Coimbra", "Benevento", "Ghent", "Oslo", "Toulouse"}
    )


def test_site_ref_rejects_invented_city() -> None:
    with pytest.raises(DomainValidationError):
        SiteRef(site_id="x", city="Lisbon", display_name="Lisbon")


def test_packet_create_starts_received(coimbra_site: SiteRef, citizen: Actor) -> None:
    packet = ObservationPacket.create(
        coimbra_site, author_actor_id=citizen.actor_id
    )
    assert packet.workflow_state == WorkflowState.RECEIVED
    assert packet.site.city == "Coimbra"
    assert len(packet.packet_id) >= 16
    assert packet.confirmation is None
    assert packet.is_exportable is False
    intents = packet.pending_provenance()
    assert any(i.action == "packet.created" for i in intents)


def test_excluded_field_refused() -> None:
    with pytest.raises(InvalidFieldValue):
        FieldValue(code="bmwp", value=42)


def test_unknown_field_refused() -> None:
    with pytest.raises(InvalidFieldValue):
        FieldValue(code="invented_indicator", value="x")


def test_set_field_and_immutable_view(
    packet: ObservationPacket, citizen: Actor
) -> None:
    packet.set_field(FieldValue(code="foam", value="absent"), actor=citizen)
    assert packet.fields["foam"].value == "absent"
    with pytest.raises(TypeError):
        packet.fields["foam"] = FieldValue(code="colour", value="brown")  # type: ignore[index]


def test_ai_cannot_set_field(packet: ObservationPacket, ai_actor: Actor) -> None:
    from app.domain.errors import UnauthorizedDomainAction

    with pytest.raises(UnauthorizedDomainAction):
        packet.set_field(FieldValue(code="foam", value="present"), actor=ai_actor)
