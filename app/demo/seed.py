"""Seed labelled synthetic Coimbra AquaSignal runs (A3 fixtures + A4 AnalysisService).

Creates append-only SUCCEEDED runs:
  1) Temporal shift fixture A + contradiction fixture C (with an open case)
  2) Insufficient fixture E
  3) Stable temporal control fixture B (no temporal shift; absent vs none
     are canonicalized before detectors, so they do not conflict)

Fixture D (D_duplicate_support) is not seeded — available for tests/manual load only.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.application.analysis_service import AnalysisService
from app.application.investigation_service import InvestigationService
from app.application.reviewer_flow import DEMO_REVIEWER_ACTOR_ID
from app.demo.fixture_loader import load_fixture
from app.domain.enums import ActorType
from app.domain.signal.value_objects import TimeWindow
from app.domain.sites import get_site
from app.domain.value_objects import Actor
from app.signals.params import ContradictionParams, TemporalBaselineParams


def _params(baseline_window: TimeWindow, recent_window: TimeWindow, *, k: float = 1.0):
    return {
        "temporal_baseline_shift": TemporalBaselineParams(
            field_code="foam",
            baseline_window=baseline_window,
            recent_window=recent_window,
            minimum_baseline_samples=5,
            minimum_recent_samples=3,
            threshold_multiplier=k,
        ),
        "cross_observation_contradiction": ContradictionParams(),
    }


def seed_coimbra_demo(
    analysis: AnalysisService,
    investigation: InvestigationService,
    *,
    open_case: bool = True,
) -> list[str]:
    """Run fixture analyses for Coimbra; return new run_ids (newest last)."""
    coimbra = get_site("coimbra")
    analysis_window = TimeWindow(
        start=datetime(2026, 6, 1, tzinfo=timezone.utc),
        end=datetime(2026, 9, 30, tzinfo=timezone.utc),
    )
    baseline_window = TimeWindow(
        start=datetime(2026, 6, 1, tzinfo=timezone.utc),
        end=datetime(2026, 8, 1, tzinfo=timezone.utc),
    )
    recent_window = TimeWindow(
        start=datetime(2026, 9, 1, tzinfo=timezone.utc),
        end=datetime(2026, 9, 30, tzinfo=timezone.utc),
    )
    params = _params(baseline_window, recent_window)
    reviewer = Actor(ActorType.REVIEWER, DEMO_REVIEWER_ACTOR_ID)
    run_ids: list[str] = []

    outcome = analysis.analyze(
        site=coimbra,
        time_window=analysis_window,
        fixture_observations=list(load_fixture("A_temporal_shift"))
        + list(load_fixture("C_contradiction")),
        params=params,
    )
    run_ids.append(outcome.run.run_id)
    if open_case:
        investigation.open_case(
            site=coimbra,
            window=analysis_window,
            analysis_run_id=outcome.run.run_id,
            opened_by=reviewer,
        )

    outcome_e = analysis.analyze(
        site=coimbra,
        time_window=analysis_window,
        fixture_observations=load_fixture("E_insufficient"),
        params=params,
    )
    run_ids.append(outcome_e.run.run_id)

    outcome_b = analysis.analyze(
        site=coimbra,
        time_window=analysis_window,
        fixture_observations=load_fixture("B_stable_control"),
        params=params,
    )
    run_ids.append(outcome_b.run.run_id)
    return run_ids
