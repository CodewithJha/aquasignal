"""Phase 7 domain: NEEDS_REVIEW accept/reject, reasons, confirmed immutability."""

from __future__ import annotations

import pytest

from app.domain.enums import RejectionReasonCode, WorkflowState
from app.domain.errors import (
    ConfirmationBlocked,
    DomainValidationError,
    InvalidStateTransition,
    UnauthorizedDomainAction,
)
from app.domain.packet import ObservationPacket
from app.domain.value_objects import Actor, FieldValue
from tests.domain.conftest import foam_field, hard_flag, soft_flag, warn_flag


def _to_needs_review(
    packet: ObservationPacket, *, system: Actor, citizen: Actor, flags=None
) -> None:
    packet.set_field(foam_field(), actor=citizen)
    packet.apply_flags(flags if flags is not None else [warn_flag()], actor=system)
    packet.request_review(actor=system, reason="policy")
    assert packet.workflow_state == WorkflowState.NEEDS_REVIEW


def test_needs_review_to_confirmed_accept(
    packet: ObservationPacket, system: Actor, citizen: Actor, reviewer: Actor
) -> None:
    _to_needs_review(packet, system=system, citizen=citizen)
    snap = packet.accept_review(actor=reviewer, reason_codes=["policy_ok"])
    assert packet.workflow_state == WorkflowState.CONFIRMED
    assert packet.confirmation is not None
    assert snap.content_hash == packet.confirmation.content_hash
    assert packet.is_exportable is False


def test_needs_review_to_rejected(
    packet: ObservationPacket, system: Actor, citizen: Actor, reviewer: Actor
) -> None:
    _to_needs_review(packet, system=system, citizen=citizen)
    packet.reject(
        actor=reviewer,
        reason_code=RejectionReasonCode.INSUFFICIENT_EVIDENCE.value,
    )
    assert packet.workflow_state == WorkflowState.REJECTED


def test_reject_empty_reason_code_refused(
    packet: ObservationPacket, system: Actor, citizen: Actor, reviewer: Actor
) -> None:
    _to_needs_review(packet, system=system, citizen=citizen)
    with pytest.raises(DomainValidationError):
        packet.reject(actor=reviewer, reason_code="  ")
    assert packet.workflow_state == WorkflowState.NEEDS_REVIEW


def test_reject_unknown_reason_code_refused(
    packet: ObservationPacket, system: Actor, citizen: Actor, reviewer: Actor
) -> None:
    _to_needs_review(packet, system=system, citizen=citizen)
    with pytest.raises(DomainValidationError):
        packet.reject(actor=reviewer, reason_code="made_up_code")


def test_accept_blocked_by_standing_hard(
    packet: ObservationPacket, system: Actor, citizen: Actor, reviewer: Actor
) -> None:
    _to_needs_review(packet, system=system, citizen=citizen, flags=[hard_flag()])
    with pytest.raises(ConfirmationBlocked):
        packet.accept_review(actor=reviewer)
    assert packet.workflow_state == WorkflowState.NEEDS_REVIEW


def test_soft_block_does_not_block_accept(
    packet: ObservationPacket, system: Actor, citizen: Actor, reviewer: Actor
) -> None:
    _to_needs_review(packet, system=system, citizen=citizen, flags=[soft_flag()])
    packet.accept_review(actor=reviewer)
    assert packet.workflow_state == WorkflowState.CONFIRMED
    assert packet.standing_soft_blocks()  # still standing — finalize later blocked


def test_invalid_confirmed_to_needs_review(
    packet: ObservationPacket, system: Actor, citizen: Actor
) -> None:
    packet.set_field(foam_field(), actor=citizen)
    packet.apply_flags([], actor=system)
    packet.mark_awaiting_confirm(actor=system)
    packet.confirm(actor=citizen)
    with pytest.raises(InvalidStateTransition):
        packet.request_review(actor=system)


def test_confirmed_fields_immutable_after_accept(
    packet: ObservationPacket, system: Actor, citizen: Actor, reviewer: Actor
) -> None:
    _to_needs_review(packet, system=system, citizen=citizen)
    packet.accept_review(actor=reviewer)
    with pytest.raises(InvalidStateTransition):
        packet.replace_fields(
            {"foam": FieldValue(code="foam", value="absent")},
            actor=reviewer,
        )


def test_reviewer_edit_while_needs_review_revalidate(
    packet: ObservationPacket, system: Actor, citizen: Actor, reviewer: Actor
) -> None:
    _to_needs_review(packet, system=system, citizen=citizen, flags=[warn_flag()])
    packet.replace_fields(
        {
            "foam": FieldValue(code="foam", value="absent"),
            "colour": FieldValue(code="colour", value="clear"),
            "smell": FieldValue(code="smell", value="none"),
        },
        actor=reviewer,
    )
    assert packet.flags == ()  # cleared pending revalidate
    packet.apply_flags([warn_flag()], actor=system)
    assert packet.workflow_state == WorkflowState.NEEDS_REVIEW
    assert len(packet.flags) == 1


def test_citizen_cannot_edit_needs_review(
    packet: ObservationPacket, system: Actor, citizen: Actor
) -> None:
    _to_needs_review(packet, system=system, citizen=citizen)
    with pytest.raises(UnauthorizedDomainAction):
        packet.set_field(foam_field(), actor=citizen)


def test_ai_cannot_accept_or_reject(
    packet: ObservationPacket,
    system: Actor,
    citizen: Actor,
    ai_actor: Actor,
) -> None:
    _to_needs_review(packet, system=system, citizen=citizen)
    with pytest.raises(UnauthorizedDomainAction):
        packet.accept_review(actor=ai_actor)
    with pytest.raises(UnauthorizedDomainAction):
        packet.reject(actor=ai_actor, reason_code="other")
