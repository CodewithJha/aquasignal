"""InvestigationCase lifecycle and HumanDecision authority."""

from __future__ import annotations

import pytest

from app.domain.errors import (
    DomainValidationError,
    InvalidStateTransition,
    UnauthorizedDomainAction,
)
from app.domain.investigation.case import InvestigationCase
from app.domain.investigation.decision import HumanDecision
from app.domain.investigation.enums import CaseState, DecisionCode
from app.domain.signal.value_objects import TimeWindow
from app.domain.value_objects import Actor, SiteRef


def test_open_to_under_review_to_closed(
    coimbra_site: SiteRef, reviewer: Actor, window: TimeWindow
) -> None:
    case = InvestigationCase.open(
        site=coimbra_site,
        window=window,
        analysis_run_id="run_1",
        signal_ids=("sig_1",),
        reproducibility_ref="snap_hash_" + "f" * 54,
        opened_by=reviewer,
    )
    assert case.state is CaseState.OPEN
    case.start_review(actor=reviewer)
    assert case.state is CaseState.UNDER_REVIEW

    decision = HumanDecision.create(
        actor=reviewer,
        decision_code=DecisionCode.CONCLUDE_CHANGE_SUSPECTED,
        rationale="Evidence shift warrants follow-up collection",
        linked_signal_ids=("sig_1",),
        case_id=case.case_id,
    )
    case.close(actor=reviewer, decision=decision)
    assert case.state is CaseState.CLOSED
    assert decision.decision_id in case.decision_ids


def test_dismiss_requires_human_decision(
    coimbra_site: SiteRef, reviewer: Actor, window: TimeWindow
) -> None:
    case = InvestigationCase.open(
        site=coimbra_site,
        window=window,
        analysis_run_id="run_1",
        signal_ids=("sig_1",),
        reproducibility_ref="r" * 64,
        opened_by=reviewer,
    )
    decision = HumanDecision.create(
        actor=reviewer,
        decision_code=DecisionCode.DISMISS,
        rationale="Single noisy fixture; not actionable",
        linked_signal_ids=("sig_1",),
        case_id=case.case_id,
    )
    case.dismiss(actor=reviewer, decision=decision)
    assert case.state is CaseState.DISMISSED


def test_cannot_close_without_decision(
    coimbra_site: SiteRef, reviewer: Actor, window: TimeWindow
) -> None:
    case = InvestigationCase.open(
        site=coimbra_site,
        window=window,
        analysis_run_id="run_1",
        signal_ids=("sig_1",),
        reproducibility_ref="r" * 64,
        opened_by=reviewer,
    )
    case.start_review(actor=reviewer)
    with pytest.raises(DomainValidationError, match="HumanDecision"):
        case.close(actor=reviewer, decision=None)  # type: ignore[arg-type]


def test_illegal_open_to_closed(
    coimbra_site: SiteRef, reviewer: Actor, window: TimeWindow
) -> None:
    case = InvestigationCase.open(
        site=coimbra_site,
        window=window,
        analysis_run_id="run_1",
        signal_ids=("sig_1",),
        reproducibility_ref="r" * 64,
        opened_by=reviewer,
    )
    decision = HumanDecision.create(
        actor=reviewer,
        decision_code=DecisionCode.CONCLUDE_INSUFFICIENT,
        rationale="Need more points",
        linked_signal_ids=("sig_1",),
        case_id=case.case_id,
    )
    with pytest.raises(InvalidStateTransition):
        case.close(actor=reviewer, decision=decision)


def test_terminal_refuses_further_transitions(
    coimbra_site: SiteRef, reviewer: Actor, window: TimeWindow
) -> None:
    case = InvestigationCase.open(
        site=coimbra_site,
        window=window,
        analysis_run_id="run_1",
        signal_ids=("sig_1",),
        reproducibility_ref="r" * 64,
        opened_by=reviewer,
    )
    decision = HumanDecision.create(
        actor=reviewer,
        decision_code=DecisionCode.DISMISS,
        rationale="noise",
        linked_signal_ids=("sig_1",),
        case_id=case.case_id,
    )
    case.dismiss(actor=reviewer, decision=decision)
    with pytest.raises(InvalidStateTransition):
        case.start_review(actor=reviewer)


def test_ai_cannot_create_authoritative_decision(ai_actor: Actor) -> None:
    with pytest.raises(UnauthorizedDomainAction):
        HumanDecision.create(
            actor=ai_actor,
            decision_code=DecisionCode.NOTE,
            rationale="AI narrative",
            linked_signal_ids=("sig_1",),
            case_id="case_1",
        )


def test_ai_cannot_close_case(
    coimbra_site: SiteRef, reviewer: Actor, ai_actor: Actor, window: TimeWindow
) -> None:
    case = InvestigationCase.open(
        site=coimbra_site,
        window=window,
        analysis_run_id="run_1",
        signal_ids=("sig_1",),
        reproducibility_ref="r" * 64,
        opened_by=reviewer,
    )
    case.start_review(actor=reviewer)
    # Bypass HumanDecision.create AI check by forging is not possible on frozen Actor;
    # close still refuses non-human actor even with a pre-built decision from reviewer.
    decision = HumanDecision.create(
        actor=reviewer,
        decision_code=DecisionCode.REQUEST_MORE_EVIDENCE,
        rationale="Collect another visit",
        linked_signal_ids=("sig_1",),
        case_id=case.case_id,
    )
    with pytest.raises(UnauthorizedDomainAction):
        case.close(actor=ai_actor, decision=decision)


def test_legal_transitions_matrix() -> None:
    from app.domain.investigation.case import LEGAL_CASE_TRANSITIONS

    assert (CaseState.OPEN, CaseState.UNDER_REVIEW) in LEGAL_CASE_TRANSITIONS
    assert (CaseState.UNDER_REVIEW, CaseState.CLOSED) in LEGAL_CASE_TRANSITIONS
    assert (CaseState.OPEN, CaseState.DISMISSED) in LEGAL_CASE_TRANSITIONS
    assert (CaseState.UNDER_REVIEW, CaseState.DISMISSED) in LEGAL_CASE_TRANSITIONS
    assert (CaseState.OPEN, CaseState.CLOSED) not in LEGAL_CASE_TRANSITIONS
