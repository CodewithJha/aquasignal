"""P0.2 — HumanDecision recorded through InvestigationService and persisted."""

from __future__ import annotations

import pytest

from app.application.errors import ConcurrencyConflict, ResourceNotFound
from app.application.investigation_service import parse_decision_code
from app.domain.enums import ActorType
from app.domain.errors import (
    DomainValidationError,
    InvalidStateTransition,
    UnauthorizedDomainAction,
)
from app.domain.investigation.enums import CaseState, DecisionCode
from app.domain.value_objects import Actor
from app.demo.fixture_loader import load_fixture
from tests.application.aquasignal.conftest import make_analysis_params


@pytest.fixture
def case_record(analysis, investigation, coimbra, reviewer, analysis_window, baseline_window, recent_window):
    params = make_analysis_params(coimbra, analysis_window, baseline_window, recent_window)
    outcome = analysis.analyze(
        site=coimbra,
        time_window=analysis_window,
        fixture_observations=load_fixture("A_temporal_shift"),
        params=params,
    )
    return investigation.open_case_for_run(analysis_run_id=outcome.run.run_id, opened_by=reviewer)


def test_review_note_persists_and_moves_to_under_review(investigation, case_record, reviewer) -> None:
    saved, decision = investigation.record_decision(
        case_id=case_record.case.case_id,
        actor=reviewer,
        decision_code=DecisionCode.REQUEST_MORE_EVIDENCE,
        rationale="Need two more visits in October.",
        expected_version=case_record.version,
    )
    assert saved.case.state is CaseState.UNDER_REVIEW
    assert saved.version == case_record.version + 1

    reloaded = investigation.get_case(case_record.case.case_id)
    assert reloaded.case.decision_ids == (decision.decision_id,)
    decisions = investigation.list_decisions(case_record.case.case_id)
    assert len(decisions) == 1
    assert decisions[0].decision_code is DecisionCode.REQUEST_MORE_EVIDENCE
    assert decisions[0].rationale == "Need two more visits in October."
    assert decisions[0].actor == reviewer
    assert decisions[0].linked_signal_ids == case_record.case.signal_ids


@pytest.mark.parametrize(
    "code, state",
    [
        (DecisionCode.CONCLUDE_INSUFFICIENT, CaseState.CLOSED),
        (DecisionCode.CONCLUDE_CHANGE_SUSPECTED, CaseState.CLOSED),
        (DecisionCode.DISMISS, CaseState.DISMISSED),
    ],
)
def test_concluding_decisions_from_open(investigation, case_record, reviewer, code, state) -> None:
    saved, _ = investigation.record_decision(
        case_id=case_record.case.case_id,
        actor=reviewer,
        decision_code=code,
        rationale="Reviewed brief.",
        expected_version=case_record.version,
    )
    assert saved.case.state is state
    assert investigation.get_case(case_record.case.case_id).case.state is state


def test_terminal_case_refuses_further_decisions(investigation, case_record, reviewer) -> None:
    saved, _ = investigation.record_decision(
        case_id=case_record.case.case_id,
        actor=reviewer,
        decision_code=DecisionCode.DISMISS,
        rationale="Not actionable.",
        expected_version=case_record.version,
    )
    with pytest.raises(InvalidStateTransition):
        investigation.record_decision(
            case_id=case_record.case.case_id,
            actor=reviewer,
            decision_code=DecisionCode.NOTE,
            rationale="late note",
            expected_version=saved.version,
        )
    assert len(investigation.list_decisions(case_record.case.case_id)) == 1


def test_stale_version_is_a_conflict_and_persists_nothing(investigation, case_record, reviewer) -> None:
    investigation.record_decision(
        case_id=case_record.case.case_id,
        actor=reviewer,
        decision_code=DecisionCode.NOTE,
        rationale="first",
        expected_version=case_record.version,
    )
    with pytest.raises(ConcurrencyConflict):
        investigation.record_decision(
            case_id=case_record.case.case_id,
            actor=reviewer,
            decision_code=DecisionCode.CONCLUDE_INSUFFICIENT,
            rationale="double submit",
            expected_version=case_record.version,
        )
    decisions = investigation.list_decisions(case_record.case.case_id)
    assert [d.rationale for d in decisions] == ["first"]


def test_missing_rationale_refused(investigation, case_record, reviewer) -> None:
    with pytest.raises(DomainValidationError, match="rationale"):
        investigation.record_decision(
            case_id=case_record.case.case_id,
            actor=reviewer,
            decision_code=DecisionCode.NOTE,
            rationale="   ",
            expected_version=case_record.version,
        )
    assert investigation.list_decisions(case_record.case.case_id) == []


@pytest.mark.parametrize("raw", ["", "open", "close_everything", "water_safe"])
def test_invalid_decision_codes_refused(raw) -> None:
    with pytest.raises(DomainValidationError):
        parse_decision_code(raw)


def test_open_code_cannot_be_recorded(investigation, case_record, reviewer) -> None:
    with pytest.raises(DomainValidationError):
        investigation.record_decision(
            case_id=case_record.case.case_id,
            actor=reviewer,
            decision_code=DecisionCode.OPEN,
            rationale="x",
            expected_version=case_record.version,
        )


def test_unknown_case(investigation, reviewer) -> None:
    with pytest.raises(ResourceNotFound):
        investigation.record_decision(
            case_id="case_missing",
            actor=reviewer,
            decision_code=DecisionCode.NOTE,
            rationale="x",
            expected_version=1,
        )


@pytest.mark.parametrize(
    "actor",
    [Actor(ActorType.AI_PROVIDER, "gpt-x"), Actor(ActorType.SYSTEM, "analysis-service")],
)
def test_ai_or_system_cannot_decide_or_close(investigation, case_record, actor) -> None:
    for code in (DecisionCode.NOTE, DecisionCode.CONCLUDE_INSUFFICIENT, DecisionCode.DISMISS):
        with pytest.raises(UnauthorizedDomainAction):
            investigation.record_decision(
                case_id=case_record.case.case_id,
                actor=actor,
                decision_code=code,
                rationale="automated",
                expected_version=case_record.version,
            )
    assert investigation.get_case(case_record.case.case_id).case.state is CaseState.OPEN
    assert investigation.list_decisions(case_record.case.case_id) == []


def test_ai_cannot_open_case(investigation, case_record) -> None:
    with pytest.raises(UnauthorizedDomainAction):
        investigation.open_case_for_run(
            analysis_run_id=case_record.case.analysis_run_id,
            opened_by=Actor(ActorType.AI_PROVIDER, "gpt-x"),
        )
