"""Shared helpers for AquaSignal Phase A3 signal tests."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.domain.sites import get_site
from app.domain.signal.value_objects import TimeWindow
from app.signals.models import AnalysisContext
from app.signals.params import ContradictionParams, TemporalBaselineParams


@pytest.fixture
def coimbra():
    return get_site("coimbra")


@pytest.fixture
def analysis_window() -> TimeWindow:
    return TimeWindow(
        start=datetime(2026, 6, 1, tzinfo=timezone.utc),
        end=datetime(2026, 9, 30, tzinfo=timezone.utc),
    )


@pytest.fixture
def baseline_window() -> TimeWindow:
    return TimeWindow(
        start=datetime(2026, 6, 1, tzinfo=timezone.utc),
        end=datetime(2026, 8, 1, tzinfo=timezone.utc),
    )


@pytest.fixture
def recent_window() -> TimeWindow:
    return TimeWindow(
        start=datetime(2026, 9, 1, tzinfo=timezone.utc),
        end=datetime(2026, 9, 30, tzinfo=timezone.utc),
    )


def make_temporal_context(
    coimbra,
    analysis_window: TimeWindow,
    baseline_window: TimeWindow,
    recent_window: TimeWindow,
    *,
    field_code: str = "foam",
    min_baseline: int = 5,
    min_recent: int = 3,
    k: float = 3.0,
    scale: str = "mad",
) -> AnalysisContext:
    params = TemporalBaselineParams(
        field_code=field_code,
        baseline_window=baseline_window,
        recent_window=recent_window,
        minimum_baseline_samples=min_baseline,
        minimum_recent_samples=min_recent,
        threshold_multiplier=k,
        scale=scale,  # type: ignore[arg-type]
    )
    return AnalysisContext(
        site=coimbra,
        time_window=analysis_window,
        params={"temporal_baseline_shift": params},
    )


def make_contradiction_context(
    coimbra,
    analysis_window: TimeWindow,
    **param_kwargs,
) -> AnalysisContext:
    return AnalysisContext(
        site=coimbra,
        time_window=analysis_window,
        params={
            "cross_observation_contradiction": ContradictionParams(**param_kwargs),
        },
    )
