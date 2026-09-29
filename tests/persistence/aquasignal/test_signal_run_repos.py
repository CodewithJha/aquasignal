"""AquaSignal A2 — signal / analysis-run repository tests."""

from __future__ import annotations

import pytest

from app.application.errors import ImmutableAnalysisRun, ResourceNotFound
from app.domain.investigation.enums import AnalysisRunStatus
from tests.persistence.aquasignal.conftest import (
    make_fixture_evidence,
    make_packet_evidence,
    make_run,
    make_signal,
    make_snapshot,
)


def _seed_run_and_evidence(uow, coimbra, observed_at, window):
    e1 = make_packet_evidence(coimbra, observed_at, eid="ev_s1")
    e2 = make_fixture_evidence(coimbra, observed_at, eid="ev_s2")
    snap = make_snapshot(("ev_s1", "ev_s2"), sid="snap_sig")
    run = make_run(snapshot_hash=snap.snapshot_hash, run_id="run_sig")
    uow.evidence_items.save(e1)
    uow.evidence_items.save(e2)
    uow.evidence_snapshots.save(snap)
    uow.analysis_runs.save(run)
    return snap, run, ("ev_s1", "ev_s2")


def test_signal_metrics_explanation_and_evidence_links(
    uow_factory, coimbra, observed_at, window
) -> None:
    with uow_factory() as uow:
        snap, run, eids = _seed_run_and_evidence(uow, coimbra, observed_at, window)
        signal = make_signal(
            site=coimbra,
            window=window,
            run_id=run.run_id,
            evidence_ids=eids,
            signal_id="sig_1",
        )
        saved = uow.environmental_signals.save(signal)
        uow.commit()

    assert saved.metrics["delta"] == 0.4
    assert saved.explanation["threshold"] == 0.3
    assert saved.evidence_ids == eids
    assert saved.detector_version.value == "1.0.0"

    with uow_factory() as uow:
        loaded = uow.environmental_signals.require("sig_1")
        assert loaded.summary.startswith("Possible temporal shift")
        assert uow.environmental_signals.list_evidence_ids("sig_1") == list(eids)
        for_run = uow.environmental_signals.list_for_run(run.run_id)
        assert [s.signal_id for s in for_run] == ["sig_1"]
        with pytest.raises(ResourceNotFound):
            uow.environmental_signals.require("sig_missing")
        uow.commit()


def test_analysis_run_lifecycle_and_immutable_success(
    uow_factory, coimbra, observed_at, window
) -> None:
    with uow_factory() as uow:
        snap, run, eids = _seed_run_and_evidence(uow, coimbra, observed_at, window)
        signal = make_signal(
            site=coimbra,
            window=window,
            run_id=run.run_id,
            evidence_ids=eids,
            signal_id="sig_life",
        )
        uow.environmental_signals.save(signal)
        run.record_signal("sig_life")
        uow.analysis_runs.save(run)
        uow.commit()

    with uow_factory() as uow:
        loaded = uow.analysis_runs.require(run.run_id)
        assert loaded.status is AnalysisRunStatus.STARTED
        assert loaded.signals_produced == ("sig_life",)
        loaded.succeed(signals_produced=("sig_life",))
        uow.analysis_runs.save(loaded)
        uow.commit()

    with uow_factory() as uow:
        done = uow.analysis_runs.require(run.run_id)
        assert done.status is AnalysisRunStatus.SUCCEEDED
        assert done.finished_at is not None
        # No silent overwrite of successful run.
        done_again = uow.analysis_runs.require(run.run_id)
        with pytest.raises(ImmutableAnalysisRun):
            uow.analysis_runs.save(done_again)
        uow.rollback()

    with uow_factory() as uow:
        runs = uow.analysis_runs.list_for_snapshot_hash(snap.snapshot_hash)
        assert [r.run_id for r in runs] == [run.run_id]
        assert uow.analysis_runs.list_signal_ids(run.run_id) == ["sig_life"]
        with pytest.raises(ResourceNotFound):
            uow.analysis_runs.require("run_missing")
        uow.commit()


def test_analysis_run_fail_then_immutable(
    uow_factory, coimbra, observed_at, window
) -> None:
    with uow_factory() as uow:
        snap, run, _ = _seed_run_and_evidence(uow, coimbra, observed_at, window)
        run.fail(error="detector boom")
        uow.analysis_runs.save(run)
        uow.commit()

    with uow_factory() as uow:
        failed = uow.analysis_runs.require(run.run_id)
        assert failed.status is AnalysisRunStatus.FAILED
        assert failed.error == "detector boom"
        with pytest.raises(ImmutableAnalysisRun):
            uow.analysis_runs.save(failed)
        uow.rollback()
