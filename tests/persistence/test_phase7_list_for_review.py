"""Phase 7 repo: list_for_review ordering and filters."""

from __future__ import annotations

from app.domain.enums import WorkflowState
from app.domain.packet import ObservationPacket
from app.domain.value_objects import FieldValue
from tests.persistence.conftest import foam


def test_list_for_review_oldest_first_and_filter(uow_factory, coimbra, citizen, system):
    ids: list[str] = []
    for i in range(3):
        packet = ObservationPacket.create(
            coimbra,
            author_actor_id=citizen.actor_id,
            submitter_display=f"c{i}",
        )
        packet.set_field(foam(), actor=citizen)
        packet.apply_flags([], actor=system)
        packet.request_review(actor=system, reason=f"q{i}")
        with uow_factory() as uow:
            uow.packets.save(packet, expected_revision=0)
            intents = packet.drain_provenance_intents()
            if intents:
                uow.provenance.append_many(intents)
            uow.commit()
        ids.append(packet.packet_id)

    # One FLAGGED (should not appear)
    flagged = ObservationPacket.create(coimbra, author_actor_id=citizen.actor_id)
    flagged.set_field(FieldValue(code="foam", value="present"), actor=citizen)
    flagged.apply_flags([], actor=system)
    with uow_factory() as uow:
        uow.packets.save(flagged, expected_revision=0)
        uow.provenance.append_many(flagged.drain_provenance_intents())
        uow.commit()

    with uow_factory() as uow:
        items = uow.packets.list_for_review(states=("NEEDS_REVIEW",), limit=50)

    assert [i.packet_id for i in items] == ids
    assert all(i.workflow_state == WorkflowState.NEEDS_REVIEW.value for i in items)
    assert flagged.packet_id not in {i.packet_id for i in items}
    assert items[0].site_ref_id == coimbra.site_id
    assert items[0].review_reason
