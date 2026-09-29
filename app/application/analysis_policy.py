"""Default analysis scope for site analysis of FINALIZED ConfirmGate evidence.

Windows are derived from the evidence timestamps, never from the wall clock,
so the same evidence set always yields the same parameters_hash.

  analysis_end   = latest observed_at + 1s   (half-open window includes it)
  recent_window  = [analysis_end - 30 days, analysis_end)
  baseline       = [recent_start - 90 days, recent_start)
  analysis_start = min(earliest observed_at, baseline_start)

Temporal field is ``foam`` (required-for-finalize and ordinal). Sample minima
and threshold multiplier are the TemporalBaselineParams defaults; contradiction
uses ContradictionParams defaults.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from app.domain.signal.value_objects import TimeWindow
from app.signals.params import ContradictionParams, TemporalBaselineParams

DEFAULT_TEMPORAL_FIELD = "foam"
RECENT_SPAN = timedelta(days=30)
BASELINE_SPAN = timedelta(days=90)
END_PADDING = timedelta(seconds=1)


@dataclass(frozen=True, slots=True)
class AnalysisScope:
    time_window: TimeWindow
    params: dict[str, Any]


def default_scope_for(observed_at: Sequence[datetime]) -> AnalysisScope:
    if not observed_at:
        raise ValueError("default analysis scope requires at least one timestamp")
    end = max(observed_at) + END_PADDING
    recent = TimeWindow(start=end - RECENT_SPAN, end=end)
    baseline = TimeWindow(start=recent.start - BASELINE_SPAN, end=recent.start)
    start = min(min(observed_at), baseline.start)
    return AnalysisScope(
        time_window=TimeWindow(start=start, end=end),
        params={
            "temporal_baseline_shift": TemporalBaselineParams(
                field_code=DEFAULT_TEMPORAL_FIELD,
                baseline_window=baseline,
                recent_window=recent,
            ),
            "cross_observation_contradiction": ContradictionParams(),
        },
    )
