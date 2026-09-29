"""Exporter must refuse packets that are not FINALIZED."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.domain.enums import ActorType, WorkflowState
from app.domain.packet import ObservationPacket
from app.domain.value_objects import Actor, FieldValue, SiteRef
from app.fhir.exporter import FhirExportRefused, export_bundle


def _site() -> SiteRef:
    return SiteRef(
        site_id="coimbra",
        city="Coimbra",
        display_name="Coimbra, Portugal",
        fhir_location_identifier="coimbra",
    )


def _packet_in_state(state: WorkflowState) -> ObservationPacket:
    """Drive the real state machine to the requested non-arbitrary state."""
    site = _site()
    citizen = Actor(ActorType.CITIZEN, "t")
    system = Actor(ActorType.SYSTEM, "t")
    packet = ObservationPacket.create(
        site,
        author_actor_id=citizen.actor_id,
        submitter_display="Demo Citizen",
        effective_at=datetime(2026, 9, 21, tzinfo=timezone.utc),
    )

    if state == WorkflowState.RECEIVED:
        return packet

    packet.set_field(FieldValue(code="foam", value="present"), actor=citizen)
    packet.set_field(FieldValue(code="colour", value="clear"), actor=citizen)
    packet.set_field(FieldValue(code="smell", value="none"), actor=citizen)
    packet.apply_flags([], actor=system)

    if state == WorkflowState.FLAGGED:
        return packet
    if state == WorkflowState.REJECTED:
        packet.reject(actor=system, reason_code="other", explanation="test")
        return packet
    if state == WorkflowState.WITHDRAWN:
        packet.withdraw(actor=citizen)
        return packet
    if state == WorkflowState.NEEDS_REVIEW:
        packet.request_review(actor=system)
        return packet

    packet.mark_awaiting_confirm(actor=system)
    if state == WorkflowState.AWAITING_CONFIRM:
        return packet

    packet.confirm(actor=citizen)
    if state == WorkflowState.CONFIRMED:
        return packet

    if state == WorkflowState.FINALIZED:
        packet.finalize(actor=system)
        return packet

    raise AssertionError(f"unsupported state {state}")


@pytest.mark.parametrize(
    "state",
    [
        WorkflowState.RECEIVED,
        WorkflowState.FLAGGED,
        WorkflowState.AWAITING_CONFIRM,
        WorkflowState.NEEDS_REVIEW,
        WorkflowState.CONFIRMED,
        WorkflowState.REJECTED,
        WorkflowState.WITHDRAWN,
    ],
)
def test_export_refuses_non_finalized(state: WorkflowState) -> None:
    packet = _packet_in_state(state)
    assert packet.workflow_state == state
    with pytest.raises(FhirExportRefused):
        export_bundle(packet)


def test_export_allows_finalized_without_preliminary() -> None:
    packet = _packet_in_state(WorkflowState.FINALIZED)
    bundle = export_bundle(packet)
    assert bundle["resourceType"] == "Bundle"
    assert bundle["type"] == "collection"
    for entry in bundle.get("entry") or []:
        resource = entry.get("resource") or {}
        if resource.get("resourceType") == "Observation":
            assert resource.get("status") != "preliminary"
            assert resource.get("status") == "final"
