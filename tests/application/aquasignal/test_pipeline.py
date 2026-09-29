"""A4 — full analysis pipeline, hashing, rollback, optional case open."""

from __future__ import annotations

import pytest

from app.application.errors import PersistenceFailure
from app.application.params_hash import hash_analysis_parameters
from app.domain.enums import WorkflowState
from app.domain.evidence.snapshot import compute_snapshot_hash
from app.domain.investigation.enums import AnalysisRunStatus, CaseState
from app.persistence.unit_of_work import SqliteUnitOfWork
from app.signals.registry import DETECTOR_SET_VERSION
from tests.application.aquasignal.conftest import (
    build_packet,
    make_analysis_params,
    persist_packet,
)
from tests.signals.fixture_loader import load_fixture


def test_full_pipeline_persist_and_reload(
    analysis,
    observation,
    investigation,
    uow_factory,
    coimbra,
    citizen,
    system,
    reviewer,
    analysis_window,
    baseline_window,
    recent_window,
) -> None:
    # Two FINALIZED packets that conflict on foam + temporal fixture series.
    p_hi = build_packet(
        site=coimbra,
        citizen=citizen,
        system=system,
        state=WorkflowState.FINALIZED,
        foam="present",
        packet_id="a4pkthi000001",
    )
    p_lo = build_packet(
        site=coimbra,
        citizen=citizen,
        system=system,
        state=WorkflowState.FINALIZED,
        foam="absent",
        packet_id="a4pktlo000002",
    )
    persist_packet(observation, p_hi)
    persist_packet(observation, p_lo)
    fixtures = load_fixture("A_temporal_shift")
    params = make_analysis_params(
        coimbra, analysis_window, baseline_window, recent_window, k=1.0
    )

    outcome = analysis.analyze(
        site=coimbra,
        time_window=analysis_window,
        packet_ids=[p_hi.packet_id, p_lo.packet_id],
        fixture_observations=fixtures,
        params=params,
    )

    assert outcome.run.status is AnalysisRunStatus.SUCCEEDED
    assert outcome.detector_set_version == DETECTOR_SET_VERSION
    assert outcome.parameters_hash == hash_analysis_parameters(params)
    assert outcome.snapshot.snapshot_hash == compute_snapshot_hash(
        outcome.snapshot.ordered_evidence_ids,
        outcome.snapshot.source_manifest,
    )
    assert len(outcome.signals) >= 1
    assert any(s.signal_type.value == "temporal_shift" for s in outcome.signals) or any(
        s.signal_type.value == "contradiction" for s in outcome.signals
    )

    # Reload via service + UoW
    loaded_run = analysis.get_run(outcome.run.run_id)
    assert loaded_run.status is AnalysisRunStatus.SUCCEEDED
    assert loaded_run.parameters_hash == outcome.parameters_hash
    reloaded_signals = analysis.list_signals_for_run(outcome.run.run_id)
    assert {s.signal_id for s in reloaded_signals} == {
        s.signal_id for s in outcome.signals
    }
    reloaded_rels = analysis.list_relations_for_run(outcome.run.run_id)
    assert len(reloaded_rels) == len(outcome.relations)
    snap = analysis.get_snapshot(outcome.snapshot.snapshot_id)
    assert snap.snapshot_hash == outcome.snapshot.snapshot_hash

    # Append-only: second run gets a new id; prior SUCCEEDED untouched.
    outcome2 = analysis.analyze(
        site=coimbra,
        time_window=analysis_window,
        packet_ids=[p_hi.packet_id, p_lo.packet_id],
        fixture_observations=fixtures,
        params=params,
    )
    assert outcome2.run.run_id != outcome.run.run_id
    assert analysis.get_run(outcome.run.run_id).status is AnalysisRunStatus.SUCCEEDED

    with uow_factory() as uow:
        history = uow.analysis_runs.list_for_snapshot_hash(outcome.snapshot.snapshot_hash)
        # Same evidence ordering → same snapshot hash across runs.
        assert len(history) >= 2
        uow.commit()

    # Optional InvestigationCase (not forced by analyze)
    case_rec = investigation.open_case(
        site=coimbra,
        window=analysis_window,
        analysis_run_id=outcome.run.run_id,
        opened_by=reviewer,
    )
    assert case_rec.case.state is CaseState.OPEN
    assert case_rec.case.analysis_run_id == outcome.run.run_id

    # Provenance on ConfirmGate packets
    events = observation.list_provenance(p_hi.packet_id)
    actions = {e.action for e in events}
    assert "analysis.snapshot_built" in actions
    assert "analysis.run_succeeded" in actions


def test_params_and_snapshot_hash_reproducible(
    coimbra, analysis_window, baseline_window, recent_window
) -> None:
    params = make_analysis_params(
        coimbra, analysis_window, baseline_window, recent_window
    )
    h1 = hash_analysis_parameters(params)
    h2 = hash_analysis_parameters(params)
    assert h1 == h2
    assert len(h1) == 64

    # Order of keys in a plain dict must not matter after canonicalize
    shuffled = {
        "cross_observation_contradiction": params["cross_observation_contradiction"],
        "temporal_baseline_shift": params["temporal_baseline_shift"],
    }
    assert hash_analysis_parameters(shuffled) == h1

    ids = ("b", "a")
    manifest = {"n": 2, "site_id": "coimbra"}
    assert compute_snapshot_hash(ids, manifest) == compute_snapshot_hash(ids, dict(manifest))


def test_transaction_rollback_on_mid_pipeline_failure(
    analysis,
    observation,
    uow_factory,
    coimbra,
    citizen,
    system,
    analysis_window,
    baseline_window,
    recent_window,
) -> None:
    packet = build_packet(
        site=coimbra,
        citizen=citizen,
        system=system,
        state=WorkflowState.FINALIZED,
        packet_id="a4rollpkt0001",
    )
    persist_packet(observation, packet)
    fixtures = load_fixture("C_contradiction")
    params = make_analysis_params(
        coimbra, analysis_window, baseline_window, recent_window
    )

    # Monkeypatch UoW factory to fail after partial writes before commit.
    real_factory = uow_factory
    boom_seen = {"n": 0}

    class BoomUow(SqliteUnitOfWork):
        def commit(self) -> None:  # noqa: D102
            boom_seen["n"] += 1
            raise PersistenceFailure("intentional mid-pipeline commit failure")

    def boom_factory():
        base = real_factory()
        return BoomUow(base._conn)  # noqa: SLF001

    analysis._uow_factory = boom_factory  # noqa: SLF001

    with pytest.raises(PersistenceFailure, match="intentional"):
        analysis.analyze(
            site=coimbra,
            time_window=analysis_window,
            packet_ids=[packet.packet_id],
            fixture_observations=fixtures,
            params=params,
        )

    assert boom_seen["n"] == 1

    # Restore factory and verify nothing AquaSignal was durable.
    analysis._uow_factory = real_factory  # noqa: SLF001
    with real_factory() as uow:
        assert uow.evidence_items.get(packet.packet_id) is None
        assert uow.analysis_runs.list_for_snapshot_hash("x") == []
        # No snapshots at all for this site run
        rows = uow._conn.execute(  # noqa: SLF001
            "SELECT COUNT(*) AS c FROM evidence_snapshots"
        ).fetchone()
        assert int(rows["c"]) == 0
        uow.commit()
