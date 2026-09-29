"""P4.3 — site run history marks synthetic-fixture vs finalized-observation runs."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.application.investigation_brief import InvestigationBriefService, list_item_to_api
from app.composition import build_services, reset_services, set_services
from app.demo.fixture_loader import load_fixture
from app.domain.enums import WorkflowState
from app.flags.engine import DeterministicFlagEngine
from app.main import app
from tests.application.aquasignal.conftest import (
    build_packet,
    make_analysis_params,
    persist_packet,
)

T0 = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)


def _runs(analysis, observation, coimbra, citizen, system, windows) -> dict[str, str]:
    analysis_window, baseline_window, recent_window = windows
    params = make_analysis_params(coimbra, analysis_window, baseline_window, recent_window)
    pid = persist_packet(
        observation,
        build_packet(
            site=coimbra,
            citizen=citizen,
            system=system,
            state=WorkflowState.FINALIZED,
            effective_at=T0,
        ),
    )
    finalized = analysis.analyze_finalized_for_site(site=coimbra).run.run_id
    synthetic = analysis.analyze(
        site=coimbra,
        time_window=analysis_window,
        fixture_observations=load_fixture("A_temporal_shift"),
        params=params,
    ).run.run_id
    mixed = analysis.analyze(
        site=coimbra,
        time_window=analysis_window,
        packet_ids=[pid],
        fixture_observations=load_fixture("A_temporal_shift"),
        params=params,
    ).run.run_id
    return {finalized: "FINALIZED OBSERVATIONS", synthetic: "SYNTHETIC FIXTURE", mixed: "MIXED"}


def test_list_items_carry_evidence_origin(
    analysis, observation, uow_factory, coimbra, citizen, system,
    analysis_window, baseline_window, recent_window,
) -> None:
    expected = _runs(
        analysis, observation, coimbra, citizen, system,
        (analysis_window, baseline_window, recent_window),
    )
    rows = InvestigationBriefService(uow_factory).list_analyses_for_site("coimbra")
    assert {r.run_id: r.evidence_origin for r in rows} == expected
    assert {r.run_id: list_item_to_api(r)["evidence_origin"] for r in rows} == expected


def test_site_page_shows_origin_badges(
    settings, analysis, observation, coimbra, citizen, system,
    analysis_window, baseline_window, recent_window,
) -> None:
    _runs(
        analysis, observation, coimbra, citizen, system,
        (analysis_window, baseline_window, recent_window),
    )
    reset_services()
    set_services(build_services(settings=settings, flag_engine=DeterministicFlagEngine()))
    try:
        with TestClient(app) as client:
            html = client.get("/investigate/sites/coimbra").text
    finally:
        reset_services()
    assert "Evidence source" in html
    assert "SYNTHETIC FIXTURE" in html
    assert "FINALIZED OBSERVATIONS" in html
    assert "MIXED" in html
