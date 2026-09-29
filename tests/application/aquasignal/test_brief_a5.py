"""A5 — InvestigationBriefService retrieval over persisted A4 results."""

from __future__ import annotations

import pytest

from app.application.errors import ResourceNotFound
from app.application.investigation_brief import InvestigationBriefService
from app.domain.enums import WorkflowState
from app.domain.investigation.enums import AnalysisRunStatus
from tests.application.aquasignal.conftest import (
    build_packet,
    make_analysis_params,
    persist_packet,
)
from tests.signals.fixture_loader import load_fixture


@pytest.fixture
def brief(uow_factory) -> InvestigationBriefService:
    return InvestigationBriefService(uow_factory)


def test_list_and_brief_for_fixture_analysis(
    analysis,
    brief,
    investigation,
    coimbra,
    analysis_window,
    baseline_window,
    recent_window,
    reviewer,
) -> None:
    fixtures = load_fixture("A_temporal_shift") + load_fixture("C_contradiction")
    params = make_analysis_params(
        coimbra, analysis_window, baseline_window, recent_window
    )
    outcome = analysis.analyze(
        site=coimbra,
        time_window=analysis_window,
        fixture_observations=fixtures,
        params=params,
    )
    investigation.open_case(
        site=coimbra,
        window=analysis_window,
        analysis_run_id=outcome.run.run_id,
        opened_by=reviewer,
    )

    rows = brief.list_analyses_for_site("coimbra")
    assert any(r.run_id == outcome.run.run_id for r in rows)
    row = next(r for r in rows if r.run_id == outcome.run.run_id)
    assert row.status == AnalysisRunStatus.SUCCEEDED.value
    assert row.evidence_count >= 2
    assert row.signal_count == len(outcome.signals)
    assert row.detector_set_version == outcome.detector_set_version

    detail = brief.get_brief(outcome.run.run_id)
    assert detail.site_id == "coimbra"
    assert detail.failed is False
    assert detail.evidence_count == row.evidence_count
    assert any(e.is_synthetic for e in detail.evidence)
    assert all("SYNTHETIC" in e.source_label.upper() for e in detail.evidence if e.is_synthetic)
    assert detail.reproducibility.snapshot_hash == outcome.snapshot.snapshot_hash
    assert detail.reproducibility.parameters_hash == outcome.parameters_hash
    assert detail.reproducibility.run_id == outcome.run.run_id
    assert len(detail.cases) == 1
    assert detail.stance.conflicting >= 0
    # No composite score fields on brief
    assert not hasattr(detail, "trust_score")
    assert not hasattr(detail, "confidence")


def test_confirmgate_packet_links_and_labels(
    analysis,
    observation,
    brief,
    coimbra,
    citizen,
    system,
    analysis_window,
    baseline_window,
    recent_window,
) -> None:
    p_hi = build_packet(
        site=coimbra,
        citizen=citizen,
        system=system,
        state=WorkflowState.FINALIZED,
        foam="present",
        packet_id="a5pkthi000001",
    )
    p_lo = build_packet(
        site=coimbra,
        citizen=citizen,
        system=system,
        state=WorkflowState.FINALIZED,
        foam="absent",
        packet_id="a5pktlo000002",
    )
    persist_packet(observation, p_hi)
    persist_packet(observation, p_lo)
    params = make_analysis_params(
        coimbra, analysis_window, baseline_window, recent_window
    )
    outcome = analysis.analyze(
        site=coimbra,
        time_window=analysis_window,
        packet_ids=[p_hi.packet_id, p_lo.packet_id],
        params=params,
    )
    detail = brief.get_brief(outcome.run.run_id)
    cg = [e for e in detail.evidence if e.source_class == "confirmgate_packet"]
    assert len(cg) == 2
    for e in cg:
        assert e.confirmgate_observation_url == f"/observation/{e.evidence_id}"
        assert "ConfirmGate" in e.source_label
        assert e.is_synthetic is False
        assert "foam" in e.fields

    if detail.contradictions:
        pair = detail.contradictions[0]
        assert pair.left.evidence_id != pair.right.evidence_id
        assert "wrong" not in pair.message.lower()


def test_insufficient_and_nosignal_states(
    analysis,
    brief,
    coimbra,
    analysis_window,
    baseline_window,
    recent_window,
) -> None:
    params = make_analysis_params(
        coimbra, analysis_window, baseline_window, recent_window
    )
    insuff = analysis.analyze(
        site=coimbra,
        time_window=analysis_window,
        fixture_observations=load_fixture("E_insufficient"),
        params=params,
    )
    brief_i = brief.get_brief(insuff.run.run_id)
    assert brief_i.stance.insufficient >= 1 or any(
        s.is_insufficient for s in brief_i.signals
    )
    assert brief_i.failed is False

    stable = analysis.analyze(
        site=coimbra,
        time_window=analysis_window,
        fixture_observations=load_fixture("B_stable_control"),
        params=params,
    )
    brief_b = brief.get_brief(stable.run.run_id)
    # Stable control: may be no_signal_success or only non-conflict signals
    text = " ".join(s.summary.lower() for s in brief_b.signals)
    assert "safe" not in text
    assert "pollution" not in text


def test_missing_run_raises(brief) -> None:
    with pytest.raises(ResourceNotFound):
        brief.get_brief("run_does_not_exist")


def test_api_serializers_omit_scores(
    analysis,
    brief,
    coimbra,
    analysis_window,
    baseline_window,
    recent_window,
) -> None:
    from app.application.investigation_brief import brief_to_api_dict

    params = make_analysis_params(
        coimbra, analysis_window, baseline_window, recent_window
    )
    outcome = analysis.analyze(
        site=coimbra,
        time_window=analysis_window,
        fixture_observations=load_fixture("C_contradiction"),
        params=params,
    )
    payload = brief_to_api_dict(brief.get_brief(outcome.run.run_id))
    blob = str(payload).lower()
    assert "trust" not in blob
    assert "confidence" not in blob
    assert "pollution" not in blob
    assert "pathogen" not in blob
    assert "counts" in payload
    assert "reproducibility" in payload
