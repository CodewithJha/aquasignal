"""Legal and illegal workflow transitions."""

from __future__ import annotations

import pytest

from app.domain.enums import WorkflowState
from app.domain.errors import (
    InvalidStateTransition,
    UnauthorizedDomainAction,
)
from app.domain.packet import LEGAL_TRANSITIONS, ObservationPacket
from app.domain.value_objects import Actor
from tests.domain.conftest import (
    foam_field,
    hard_flag,
    reach_awaiting_confirm,
    reach_confirmed,
    warn_flag,
)


def test_legal_transitions_matrix_covers_user_contract() -> None:
    expected = {
        (WorkflowState.RECEIVED, WorkflowState.FLAGGED),
        (WorkflowState.FLAGGED, WorkflowState.AWAITING_CONFIRM),
        (WorkflowState.FLAGGED, WorkflowState.NEEDS_REVIEW),
        (WorkflowState.FLAGGED, WorkflowState.REJECTED),
        (WorkflowState.AWAITING_CONFIRM, WorkflowState.CONFIRMED),
        (WorkflowState.NEEDS_REVIEW, WorkflowState.CONFIRMED),
        (WorkflowState.NEEDS_REVIEW, WorkflowState.REJECTED),
        (WorkflowState.CONFIRMED, WorkflowState.FINALIZED),
        (WorkflowState.RECEIVED, WorkflowState.WITHDRAWN),
        (WorkflowState.FLAGGED, WorkflowState.WITHDRAWN),
        (WorkflowState.AWAITING_CONFIRM, WorkflowState.WITHDRAWN),
        (WorkflowState.NEEDS_REVIEW, WorkflowState.WITHDRAWN),
        (WorkflowState.CONFIRMED, WorkflowState.WITHDRAWN),
    }
    assert LEGAL_TRANSITIONS == expected
    # No preliminary / fhir_preliminary / unconfirm edges.
    assert (WorkflowState.CONFIRMED, WorkflowState.AWAITING_CONFIRM) not in LEGAL_TRANSITIONS
    assert (WorkflowState.CONFIRMED, WorkflowState.NEEDS_REVIEW) not in LEGAL_TRANSITIONS
    assert (WorkflowState.RECEIVED, WorkflowState.FINALIZED) not in LEGAL_TRANSITIONS


def test_happy_path(
    packet: ObservationPacket, system: Actor, citizen: Actor
) -> None:
    packet.set_field(foam_field(), actor=citizen)
    packet.apply_flags([], actor=system)
    assert packet.workflow_state == WorkflowState.FLAGGED
    packet.mark_awaiting_confirm(actor=system)
    assert packet.workflow_state == WorkflowState.AWAITING_CONFIRM
    packet.confirm(actor=citizen)
    assert packet.workflow_state == WorkflowState.CONFIRMED
    packet.finalize(actor=system)
    assert packet.workflow_state == WorkflowState.FINALIZED
    assert packet.is_exportable is True


def test_flagged_to_rejected(
    packet: ObservationPacket, system: Actor, citizen: Actor
) -> None:
    packet.set_field(foam_field(), actor=citizen)
    packet.apply_flags([hard_flag()], actor=system)
    packet.reject(actor=system, reason_code="prohibited_claim")
    assert packet.workflow_state == WorkflowState.REJECTED


def test_flagged_to_needs_review_then_accept(
    packet: ObservationPacket, system: Actor, citizen: Actor, reviewer: Actor
) -> None:
    packet.set_field(foam_field(), actor=citizen)
    packet.apply_flags([warn_flag()], actor=system)
    packet.request_review(actor=system, reason="policy")
    assert packet.workflow_state == WorkflowState.NEEDS_REVIEW
    packet.accept_review(actor=reviewer, reason_codes=["ok"])
    assert packet.workflow_state == WorkflowState.CONFIRMED


def test_needs_review_reject(
    packet: ObservationPacket, system: Actor, citizen: Actor, reviewer: Actor
) -> None:
    packet.set_field(foam_field(), actor=citizen)
    packet.apply_flags([], actor=system)
    packet.request_review(actor=system)
    packet.reject(actor=reviewer, reason_code="insufficient_evidence")
    assert packet.workflow_state == WorkflowState.REJECTED


@pytest.mark.parametrize(
    "stop_at",
    [
        WorkflowState.RECEIVED,
        WorkflowState.FLAGGED,
        WorkflowState.AWAITING_CONFIRM,
        WorkflowState.NEEDS_REVIEW,
        WorkflowState.CONFIRMED,
    ],
)
def test_withdraw_from_non_terminal(
    packet: ObservationPacket,
    system: Actor,
    citizen: Actor,
    stop_at: WorkflowState,
) -> None:
    if stop_at != WorkflowState.RECEIVED:
        packet.set_field(foam_field(), actor=citizen)
        packet.apply_flags([], actor=system)
    if stop_at == WorkflowState.AWAITING_CONFIRM:
        packet.mark_awaiting_confirm(actor=system)
    elif stop_at == WorkflowState.NEEDS_REVIEW:
        packet.request_review(actor=system)
    elif stop_at == WorkflowState.CONFIRMED:
        packet.mark_awaiting_confirm(actor=system)
        packet.confirm(actor=citizen)
    packet.withdraw(actor=citizen)
    assert packet.workflow_state == WorkflowState.WITHDRAWN


def test_illegal_received_to_finalized(
    packet: ObservationPacket, system: Actor
) -> None:
    with pytest.raises(InvalidStateTransition) as exc:
        packet.finalize(actor=system)
    assert exc.value.current == WorkflowState.RECEIVED
    assert exc.value.requested == WorkflowState.FINALIZED
    assert packet.workflow_state == WorkflowState.RECEIVED


def test_illegal_rejected_cannot_confirm(
    packet: ObservationPacket, system: Actor, citizen: Actor
) -> None:
    packet.set_field(foam_field(), actor=citizen)
    packet.apply_flags([hard_flag()], actor=system)
    packet.reject(actor=system, reason_code="unsupported_observation")
    with pytest.raises(InvalidStateTransition):
        packet.confirm(actor=citizen)
    assert packet.workflow_state == WorkflowState.REJECTED


def test_terminal_blocks_apply_flags(
    packet: ObservationPacket, system: Actor, citizen: Actor
) -> None:
    reach_confirmed(packet, system=system, citizen=citizen)
    packet.finalize(actor=system)
    with pytest.raises(InvalidStateTransition):
        packet.apply_flags([], actor=system)


def test_cannot_withdraw_finalized(
    packet: ObservationPacket, system: Actor, citizen: Actor
) -> None:
    reach_confirmed(packet, system=system, citizen=citizen)
    packet.finalize(actor=system)
    with pytest.raises(InvalidStateTransition):
        packet.withdraw(actor=citizen)


def test_reject_from_awaiting_confirm_illegal(
    packet: ObservationPacket, system: Actor, citizen: Actor
) -> None:
    reach_awaiting_confirm(packet, system=system, citizen=citizen)
    with pytest.raises(InvalidStateTransition):
        packet.reject(actor=system, reason_code="other", explanation="nope")


def test_citizen_cannot_apply_flags(
    packet: ObservationPacket, citizen: Actor
) -> None:
    with pytest.raises(UnauthorizedDomainAction):
        packet.apply_flags([], actor=citizen)
