"""AquaSignal A2 — investigation case / human decision repository tests."""

from __future__ import annotations

import pytest

from app.application.errors import ConcurrencyConflict, ResourceNotFound
from app.domain.investigation.enums import CaseState, DecisionCode
from tests.persistence.aquasignal.conftest import (
    make_case,
    make_decision,
    make_fixture_evidence,
    make_packet_evidence,
    make_run,
    make_signal,
    make_snapshot,
)


def _seed_openable_case(uow, coimbra, observed_at, window, reviewer):
    e1 = make_packet_evidence(coimbra, observed_at, eid="ev_c1")
    e2 = make_fixture_evidence(coimbra, observed_at, eid="ev_c2")
    snap = make_snapshot(("ev_c1", "ev_c2"), sid="snap_case")
    run = make_run(snapshot_hash=snap.snapshot_hash, run_id="run_case")
    uow.evidence_items.save(e1)
    uow.evidence_items.save(e2)
    uow.evidence_snapshots.save(snap)
    uow.analysis_runs.save(run)
    signal = make_signal(
        site=coimbra,
        window=window,
        run_id=run.run_id,
        evidence_ids=("ev_c1", "ev_c2"),
        signal_id="sig_case",
    )
    uow.environmental_signals.save(signal)
    run.succeed(signals_produced=("sig_case",))
    uow.analysis_runs.save(run)
    case = make_case(
        site=coimbra,
        window=window,
        run_id=run.run_id,
        signal_ids=("sig_case",),
        reviewer=reviewer,
        case_id="case_1",
    )
    return case, run


def test_case_transitions_and_concurrency(
    uow_factory, coimbra, observed_at, window, reviewer
) -> None:
    with uow_factory() as uow:
        case, _run = _seed_openable_case(uow, coimbra, observed_at, window, reviewer)
        rec = uow.investigation_cases.save(case, expected_version=0)
        uow.commit()
    assert rec.version == 1
    assert rec.case.state is CaseState.OPEN

    with uow_factory() as uow:
        a = uow.investigation_cases.require("case_1")
        b = uow.investigation_cases.require("case_1")
        a.case.start_review(actor=reviewer)
        uow.investigation_cases.save(a.case, expected_version=a.version)
        uow.commit()

    with uow_factory() as uow:
        b.case.start_review(actor=reviewer)
        with pytest.raises(ConcurrencyConflict):
            uow.investigation_cases.save(b.case, expected_version=b.version)
        uow.rollback()

    with uow_factory() as uow:
        loaded = uow.investigation_cases.require("case_1")
        assert loaded.case.state is CaseState.UNDER_REVIEW
        assert loaded.version == 2
        assert uow.investigation_cases.list_signal_ids("case_1") == ["sig_case"]
        site_cases = uow.investigation_cases.list_for_site("coimbra")
        assert [c.case.case_id for c in site_cases] == ["case_1"]
        with pytest.raises(ResourceNotFound):
            uow.investigation_cases.require("case_missing")
        uow.commit()


def test_decision_actor_rationale_and_case_close(
    uow_factory, coimbra, observed_at, window, reviewer
) -> None:
    with uow_factory() as uow:
        case, _run = _seed_openable_case(uow, coimbra, observed_at, window, reviewer)
        uow.investigation_cases.save(case, expected_version=0)
        case.start_review(actor=reviewer)
        rec = uow.investigation_cases.save(case, expected_version=1)
        # Decision requires case row first (FK); then link via case update.
        decision = make_decision(
            case_id=case.case_id,
            actor=reviewer,
            signal_ids=("sig_case",),
            decision_id="dec_1",
        )
        saved_dec = uow.human_decisions.save(decision)
        case.close(actor=reviewer, decision=decision)
        closed = uow.investigation_cases.save(case, expected_version=rec.version)
        uow.commit()

    assert saved_dec.actor.actor_id == "reviewer-1"
    assert saved_dec.decision_code is DecisionCode.NOTE
    assert "not a pollution" in saved_dec.rationale
    assert closed.case.state is CaseState.CLOSED
    assert closed.case.decision_ids == ("dec_1",)

    with uow_factory() as uow:
        loaded = uow.human_decisions.require("dec_1")
        assert loaded.linked_signal_ids == ("sig_case",)
        listed = uow.human_decisions.list_for_case("case_1")
        assert [d.decision_id for d in listed] == ["dec_1"]
        with pytest.raises(ResourceNotFound):
            uow.human_decisions.require("dec_missing")
        uow.commit()
