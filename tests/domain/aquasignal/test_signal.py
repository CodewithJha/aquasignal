"""EnvironmentalSignal creation — hypothesis only, non-diagnostic types."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.domain.errors import DomainValidationError
from app.domain.signal.enums import SignalType
from app.domain.signal.environmental import EnvironmentalSignal
from app.domain.signal.value_objects import DetectorId, DetectorVersion, TimeWindow
from app.domain.value_objects import SiteRef


def _window() -> TimeWindow:
    return TimeWindow(
        start=datetime(2026, 9, 1, tzinfo=timezone.utc),
        end=datetime(2026, 9, 22, tzinfo=timezone.utc),
    )


def test_create_temporal_shift_signal(coimbra_site: SiteRef) -> None:
    signal = EnvironmentalSignal.create(
        detector_id=DetectorId("temporal_baseline_shift"),
        detector_version=DetectorVersion("0.1.0"),
        signal_type=SignalType.TEMPORAL_SHIFT,
        site=coimbra_site,
        time_window=_window(),
        summary="Recent foam ordinal mean differs from baseline median",
        metrics={"baseline": 0.2, "recent": 1.5, "mad": 0.1, "k": 3.0, "n": 12},
        evidence_ids=("ev_1", "ev_2"),
        analysis_run_id="run_1",
        explanation={"rule": "median+k*MAD", "threshold": 0.5},
    )
    assert signal.signal_type is SignalType.TEMPORAL_SHIFT
    assert signal.detector_id.value == "temporal_baseline_shift"
    assert signal.analysis_run_id == "run_1"
    assert "trust" not in {k.lower() for k in signal.metrics}


def test_signal_types_are_non_diagnostic() -> None:
    forbidden_substrings = ("pollution", "pathogen", "disease", "outbreak", "trust")
    for member in SignalType:
        lowered = member.value.lower()
        for bad in forbidden_substrings:
            assert bad not in lowered, f"{member} looks diagnostic"


def test_reject_empty_summary(coimbra_site: SiteRef) -> None:
    with pytest.raises(DomainValidationError, match="summary"):
        EnvironmentalSignal.create(
            detector_id=DetectorId("x"),
            detector_version=DetectorVersion("0.1.0"),
            signal_type=SignalType.INSUFFICIENT_EVIDENCE,
            site=coimbra_site,
            time_window=_window(),
            summary="  ",
            metrics={},
            evidence_ids=("ev_1",),
            analysis_run_id="run_1",
            explanation={},
        )


def test_contradiction_and_insufficient_types_exist() -> None:
    assert SignalType.CONTRADICTION.value == "contradiction"
    assert SignalType.INSUFFICIENT_EVIDENCE.value == "insufficient_evidence"
    assert SignalType.TEMPORAL_SHIFT.value == "temporal_shift"
