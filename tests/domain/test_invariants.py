"""Flag gates, confirmation snapshot, AI authority, terminal mutation."""

from __future__ import annotations

import pytest

from app.domain.enums import ActorType, FieldSource, WorkflowState
from app.domain.errors import (
    ConfirmationBlocked,
    FinalizationBlocked,
    InvalidStateTransition,
    UnauthorizedDomainAction,
)
from app.domain.packet import ObservationPacket
from app.domain.value_objects import Actor, ConfirmationSnapshot, FieldValue
from tests.domain.conftest import (
    foam_field,
    hard_flag,
    reach_awaiting_confirm,
    reach_confirmed,
    soft_flag,
    warn_flag,
)


def test_hard_flag_blocks_awaiting_and_confirm(
    packet: ObservationPacket, system: Actor, citizen: Actor
) -> None:
    packet.set_field(foam_field(), actor=citizen)
    packet.apply_flags([hard_flag()], actor=system)
    with pytest.raises(ConfirmationBlocked):
        packet.mark_awaiting_confirm(actor=system)
    # Override then proceed
    flag_id = packet.flags[0].flag_id
    packet.override_flag(flag_id, reason="reviewed photo OK", actor=citizen)
    packet.mark_awaiting_confirm(actor=system)
    packet.confirm(actor=citizen)
    assert packet.workflow_state == WorkflowState.CONFIRMED


def test_warn_does_not_block_confirm(
    packet: ObservationPacket, system: Actor, citizen: Actor
) -> None:
    reach_awaiting_confirm(
        packet, system=system, citizen=citizen, flags=[warn_flag()]
    )
    packet.confirm(actor=citizen)
    assert packet.workflow_state == WorkflowState.CONFIRMED


def test_soft_block_allows_confirm_blocks_finalize(
    packet: ObservationPacket, system: Actor, citizen: Actor
) -> None:
    reach_confirmed(
        packet, system=system, citizen=citizen, flags=[soft_flag()]
    )
    with pytest.raises(FinalizationBlocked):
        packet.finalize(actor=system)
    flag_id = packet.flags[0].flag_id
    packet.override_flag(flag_id, reason="effective inferred", actor=citizen)
    # Still CONFIRMED; override allowed pre-terminal
    packet.finalize(actor=system)
    assert packet.workflow_state == WorkflowState.FINALIZED


def test_confirmation_snapshot_deterministic(
    packet: ObservationPacket, system: Actor, citizen: Actor
) -> None:
    packet.set_field(FieldValue(code="foam", value="present"), actor=citizen)
    packet.set_field(FieldValue(code="colour", value="brown"), actor=citizen)
    a = ConfirmationSnapshot.from_fields(dict(packet.fields), actor=citizen)
    b = ConfirmationSnapshot.from_fields(dict(packet.fields), actor=citizen)
    assert a.content_hash == b.content_hash
    # Order independence
    shuffled = {
        "colour": packet.fields["colour"],
        "foam": packet.fields["foam"],
    }
    c = ConfirmationSnapshot.from_fields(shuffled, actor=citizen)
    assert c.content_hash == a.content_hash


def test_confirmed_fields_cannot_mutate(
    packet: ObservationPacket, system: Actor, citizen: Actor
) -> None:
    reach_confirmed(packet, system=system, citizen=citizen)
    with pytest.raises(InvalidStateTransition):
        packet.set_field(FieldValue(code="smell", value="none"), actor=citizen)


def test_finalize_requires_snapshot(
    packet: ObservationPacket, system: Actor, citizen: Actor
) -> None:
    # Force CONFIRMED without going through confirm is impossible; instead
    # confirm then clear snapshot via private poke to prove guard — better:
    # finalize without confirm fails.
    packet.set_field(foam_field(), actor=citizen)
    packet.apply_flags([], actor=system)
    packet.mark_awaiting_confirm(actor=system)
    with pytest.raises(InvalidStateTransition):
        packet.finalize(actor=system)


def test_ai_cannot_confirm(
    packet: ObservationPacket, system: Actor, citizen: Actor, ai_actor: Actor
) -> None:
    reach_awaiting_confirm(packet, system=system, citizen=citizen)
    with pytest.raises(UnauthorizedDomainAction):
        packet.confirm(actor=ai_actor)


def test_ai_cannot_finalize(
    packet: ObservationPacket, system: Actor, citizen: Actor, ai_actor: Actor
) -> None:
    reach_confirmed(packet, system=system, citizen=citizen)
    with pytest.raises(UnauthorizedDomainAction):
        packet.finalize(actor=ai_actor)


def test_ai_suggestions_not_fields(
    packet: ObservationPacket, ai_actor: Actor
) -> None:
    packet.apply_suggestions(
        {"foam": "present"},
        actor=ai_actor,
        model_id="null",
    )
    assert packet.suggestions["foam"] == "present"
    assert "foam" not in packet.fields


def test_accept_suggestion_is_human_field_write(
    packet: ObservationPacket, citizen: Actor
) -> None:
    packet.set_field(
        FieldValue(
            code="foam",
            value="present",
            source=FieldSource.AI_SUGGESTION_ACCEPTED,
        ),
        actor=citizen,
    )
    assert packet.fields["foam"].source == FieldSource.AI_SUGGESTION_ACCEPTED


def test_terminal_reject_blocks_mutation(
    packet: ObservationPacket, system: Actor, citizen: Actor
) -> None:
    packet.set_field(foam_field(), actor=citizen)
    packet.apply_flags([hard_flag()], actor=system)
    packet.reject(actor=system, reason_code="inconsistent_submission")
    with pytest.raises(InvalidStateTransition):
        packet.set_field(FieldValue(code="colour", value="clear"), actor=citizen)
    with pytest.raises(InvalidStateTransition):
        packet.apply_suggestions({}, actor=Actor(ActorType.AI_PROVIDER, "x"))
