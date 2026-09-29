"""Phase 7 application: ReviewerFlowService accept/reject/edit/concurrency."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.application.errors import ConcurrencyConflict
from app.application.reviewer_flow import ReviewerFlowError
from app.application.service import ObservationService
from app.composition import build_services
from app.domain.enums import WorkflowState
from app.domain.sites import get_site
from app.domain.value_objects import FieldValue
from app.flags.engine import DeterministicFlagEngine
from app.persistence.config import DatabaseSettings


@pytest.fixture
def services(tmp_path: Path):
    return build_services(
        settings=DatabaseSettings(sqlite_path=tmp_path / "phase7.sqlite3"),
        flag_engine=DeterministicFlagEngine(),
    )


def _sensory_fields() -> dict[str, FieldValue]:
    return {
        "foam": FieldValue(code="foam", value="present"),
        "colour": FieldValue(code="colour", value="clear"),
        "smell": FieldValue(code="smell", value="none"),
    }


def _submit_and_escalate(services) -> str:
    record = services.flow.submit(
        site=get_site("coimbra"),
        fields=_sensory_fields(),
        notes="phase7 fixture",
    )
    assert record.packet.workflow_state == WorkflowState.FLAGGED
    escalated = services.reviewer.escalate(
        record.packet.packet_id, reason="demo_escalation"
    )
    assert escalated.packet.workflow_state == WorkflowState.NEEDS_REVIEW
    return escalated.packet.packet_id


def test_accept_confirm_not_finalize(services) -> None:
    packet_id = _submit_and_escalate(services)
    accepted = services.reviewer.accept(packet_id, reason_codes=["ok"])
    assert accepted.packet.workflow_state == WorkflowState.CONFIRMED
    assert accepted.packet.confirmation is not None
    # FHIR still refused
    with pytest.raises(Exception) as exc:
        services.flow.export_fhir(packet_id)
    assert "FINALIZED" in str(exc.value) or getattr(exc.value, "code", "") == (
        "export_not_finalized"
    )


def test_reject_with_reason_and_provenance(services) -> None:
    packet_id = _submit_and_escalate(services)
    rejected = services.reviewer.reject(
        packet_id,
        reason_code="insufficient_evidence",
        explanation="photo unclear",
    )
    assert rejected.packet.workflow_state == WorkflowState.REJECTED
    events = services.reviewer.list_provenance(packet_id)
    actions = [e.action for e in events]
    assert "review.queued" in actions
    assert "review.rejected" in actions
    rejected_ev = next(e for e in events if e.action == "review.rejected")
    assert rejected_ev.after and rejected_ev.after.get("reason_code") == (
        "insufficient_evidence"
    )


def test_reject_empty_reason(services) -> None:
    packet_id = _submit_and_escalate(services)
    with pytest.raises(ReviewerFlowError) as exc:
        services.reviewer.reject(packet_id, reason_code="")
    assert "reason" in exc.value.message.lower() or exc.value.code == "review_rejected"


def test_edit_revalidates_stays_needs_review(services) -> None:
    packet_id = _submit_and_escalate(services)
    edited = services.reviewer.edit(
        packet_id,
        fields={
            "foam": FieldValue(code="foam", value="absent"),
            "colour": FieldValue(code="colour", value="brown"),
            "smell": FieldValue(code="smell", value="mild"),
        },
        notes="curator tweak",
    )
    assert edited.packet.workflow_state == WorkflowState.NEEDS_REVIEW
    assert edited.packet.fields["foam"].value == "absent"
    assert edited.packet.notes == "curator tweak"
    actions = [e.action for e in services.reviewer.list_provenance(packet_id)]
    assert "fields.replaced" in actions
    assert "flags.raised" in actions


def test_accept_wrong_state(services) -> None:
    record = services.flow.submit(
        site=get_site("coimbra"), fields=_sensory_fields()
    )
    with pytest.raises(ReviewerFlowError) as exc:
        services.reviewer.accept(record.packet.packet_id)
    assert exc.value.code == "accept_not_ready"


def test_concurrency_conflict(services) -> None:
    packet_id = _submit_and_escalate(services)
    current = services.reviewer.get(packet_id)
    stale = current.revision
    # Advance revision via edit
    services.reviewer.edit(
        packet_id,
        fields=_sensory_fields(),
        expected_revision=stale,
    )
    with pytest.raises(ReviewerFlowError) as exc:
        services.reviewer.accept(packet_id, expected_revision=stale)
    assert exc.value.code == "concurrency_conflict"


def test_mutate_at_revision_raises_before_domain(tmp_path: Path) -> None:
    settings = DatabaseSettings(sqlite_path=tmp_path / "rev.sqlite3")
    services = build_services(
        settings=settings, flag_engine=DeterministicFlagEngine()
    )
    packet_id = _submit_and_escalate(services)
    obs: ObservationService = services.observation
    with pytest.raises(ConcurrencyConflict):
        obs.mutate_at_revision(packet_id, 99999, lambda p: None)


def test_list_for_review_oldest_first(services) -> None:
    ids = []
    for _ in range(3):
        ids.append(_submit_and_escalate(services))
    queue = services.reviewer.list_queue()
    assert [i.packet_id for i in queue] == ids
    assert all(i.workflow_state == "NEEDS_REVIEW" for i in queue)
    # FLAGGED-only not listed
    flagged = services.flow.submit(
        site=get_site("ghent"), fields=_sensory_fields()
    )
    queue2 = services.reviewer.list_queue()
    assert flagged.packet.packet_id not in {i.packet_id for i in queue2}
