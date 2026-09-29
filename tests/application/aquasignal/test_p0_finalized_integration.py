"""P0.1 — FINALIZED ConfirmGate observations enter AquaSignal without seed scripts."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.application.analysis_policy import default_scope_for
from app.application.errors import AnalysisOrchestrationError, EvidenceNotEligible
from app.domain.enums import ActorType, WorkflowState
from app.domain.evidence.enums import EvidenceSourceClass
from app.domain.sites import get_site
from app.domain.value_objects import Actor
from app.demo.fixture_loader import load_fixture
from tests.application.aquasignal.conftest import (
    build_packet,
    make_analysis_params,
    persist_packet,
)

T0 = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)


def _finalized(observation, site, citizen, system, *, at: datetime, foam: str = "present") -> str:
    packet = build_packet(
        site=site,
        citizen=citizen,
        system=system,
        state=WorkflowState.FINALIZED,
        effective_at=at,
        foam=foam,
    )
    return persist_packet(observation, packet)


def _rejected(observation, site, citizen, system) -> str:
    packet = build_packet(site=site, citizen=citizen, system=system, state=WorkflowState.FLAGGED)
    packet.reject(actor=system, reason_code="insufficient_evidence")
    assert packet.workflow_state is WorkflowState.REJECTED
    return persist_packet(observation, packet)


def _withdrawn(observation, site, citizen, system) -> str:
    packet = build_packet(site=site, citizen=citizen, system=system, state=WorkflowState.FLAGGED)
    packet.withdraw(actor=citizen, reason="changed my mind")
    assert packet.workflow_state is WorkflowState.WITHDRAWN
    return persist_packet(observation, packet)


def test_finalized_observation_becomes_evidence(analysis, observation, coimbra, citizen, system, uow_factory) -> None:
    pid = _finalized(observation, coimbra, citizen, system, at=T0)

    outcome = analysis.analyze_finalized_for_site(site=coimbra)

    assert outcome.snapshot.ordered_evidence_ids == (pid,)
    assert outcome.snapshot.source_manifest["packet_ids"] == [pid]
    assert outcome.snapshot.source_manifest["fixture_ids"] == []
    with uow_factory() as uow:
        item = uow.evidence_items.require(pid)
    assert item.source_class is EvidenceSourceClass.CONFIRMGATE_PACKET
    assert item.is_synthetic is False
    assert item.payload_ref == f"packet:{pid}"
    assert item.site.site_id == "coimbra"
    assert item.observed_at == T0
    assert item.fields["foam"] == "present"
    record = observation.get(pid)
    assert item.content_hash == record.packet.confirmation.content_hash


def test_site_action_excludes_unfinalized_rejected_withdrawn(
    analysis, observation, coimbra, citizen, system
) -> None:
    keep = _finalized(observation, coimbra, citizen, system, at=T0)
    confirmed = persist_packet(
        observation,
        build_packet(site=coimbra, citizen=citizen, system=system, state=WorkflowState.CONFIRMED),
    )
    rejected = _rejected(observation, coimbra, citizen, system)
    withdrawn = _withdrawn(observation, coimbra, citizen, system)

    outcome = analysis.analyze_finalized_for_site(site=coimbra)

    ids = set(outcome.snapshot.ordered_evidence_ids)
    assert ids == {keep}
    assert not ids & {confirmed, rejected, withdrawn}


@pytest.mark.parametrize("kind", ["confirmed", "rejected", "withdrawn"])
def test_explicit_non_finalized_packet_refused(
    analysis, observation, coimbra, citizen, system, analysis_window, baseline_window, recent_window, kind
) -> None:
    if kind == "confirmed":
        pid = persist_packet(
            observation,
            build_packet(site=coimbra, citizen=citizen, system=system, state=WorkflowState.CONFIRMED),
        )
    elif kind == "rejected":
        pid = _rejected(observation, coimbra, citizen, system)
    else:
        pid = _withdrawn(observation, coimbra, citizen, system)
    params = make_analysis_params(coimbra, analysis_window, baseline_window, recent_window)
    with pytest.raises(EvidenceNotEligible, match="FINALIZED"):
        analysis.analyze(site=coimbra, time_window=analysis_window, packet_ids=[pid], params=params)


def test_site_without_finalized_observations_is_refused(analysis, observation, coimbra, citizen, system) -> None:
    persist_packet(
        observation,
        build_packet(site=coimbra, citizen=citizen, system=system, state=WorkflowState.CONFIRMED),
    )
    with pytest.raises(AnalysisOrchestrationError, match="no FINALIZED"):
        analysis.analyze_finalized_for_site(site=coimbra)


def test_multiple_finalized_same_site_analyzed_other_site_excluded(
    analysis, observation, coimbra, citizen, system
) -> None:
    ids = [
        _finalized(observation, coimbra, citizen, system, at=T0 + timedelta(days=d), foam=foam)
        for d, foam in ((0, "present"), (1, "absent"), (2, "present"))
    ]
    other = _finalized(observation, get_site("ghent"), citizen, system, at=T0)

    outcome = analysis.analyze_finalized_for_site(site=coimbra)

    assert set(outcome.snapshot.ordered_evidence_ids) == set(ids)
    assert other not in outcome.snapshot.ordered_evidence_ids
    assert outcome.run.status.value == "SUCCEEDED"
    assert outcome.run.site_id == "coimbra"
    # present vs absent at the same site is surfaced as a protocol conflict.
    assert any(r.relation_type.value == "conflicts" for r in outcome.relations)


def test_provenance_identifies_source_observation(analysis, observation, coimbra, citizen, system) -> None:
    pid = _finalized(observation, coimbra, citizen, system, at=T0)
    reviewer = Actor(ActorType.REVIEWER, "reviewer-p0")

    outcome = analysis.analyze_finalized_for_site(site=coimbra, actor=reviewer)

    events = observation.list_provenance(pid)
    succeeded = [e for e in events if e.action == "analysis.run_succeeded"]
    assert len(succeeded) == 1
    assert succeeded[0].after["run_id"] == outcome.run.run_id
    assert succeeded[0].after["snapshot_hash"] == outcome.snapshot.snapshot_hash
    assert succeeded[0].actor_id == "reviewer-p0"
    built = next(e for e in events if e.action == "analysis.snapshot_built")
    assert built.after["evidence_ids"] == [pid]


def test_site_analysis_is_deterministic(analysis, observation, coimbra, citizen, system) -> None:
    for d in range(3):
        _finalized(observation, coimbra, citizen, system, at=T0 + timedelta(days=d))

    first = analysis.analyze_finalized_for_site(site=coimbra)
    second = analysis.analyze_finalized_for_site(site=coimbra)

    assert first.run.run_id != second.run.run_id  # append-only history
    assert first.snapshot.snapshot_hash == second.snapshot.snapshot_hash
    assert first.parameters_hash == second.parameters_hash
    assert first.run.time_window == second.run.time_window
    assert [s.summary for s in first.signals] == [s.summary for s in second.signals]


def test_default_scope_is_evidence_derived() -> None:
    scope = default_scope_for([T0, T0 - timedelta(days=200)])
    tb = scope.params["temporal_baseline_shift"]
    assert scope.time_window.end == T0 + timedelta(seconds=1)
    assert scope.time_window.start == T0 - timedelta(days=200)
    assert tb.recent_window.end == scope.time_window.end
    assert tb.baseline_window.end == tb.recent_window.start
    assert tb.field_code == "foam"
    with pytest.raises(ValueError):
        default_scope_for([])


def test_fixtures_still_labelled_synthetic(analysis, coimbra, analysis_window, baseline_window, recent_window) -> None:
    params = make_analysis_params(coimbra, analysis_window, baseline_window, recent_window)
    outcome = analysis.analyze(
        site=coimbra,
        time_window=analysis_window,
        fixture_observations=load_fixture("C_contradiction"),
        params=params,
    )
    assert outcome.snapshot.source_manifest["packet_ids"] == []
    assert outcome.snapshot.source_manifest["fixture_ids"]
    assert all(o.is_synthetic for o in outcome.observations)
