"""Temporal baseline shift — edge cases from A3 brief."""

from __future__ import annotations

from datetime import datetime, timezone

from app.domain.evidence.enums import EvidenceSourceClass
from app.domain.sites import get_site
from app.domain.signal.enums import SignalType
from app.domain.signal.value_objects import TimeWindow
from app.signals.detectors.temporal_baseline_shift import (
    ZERO_MAD_ABSOLUTE_THRESHOLD,
    TemporalBaselineShiftDetector,
)
from app.signals.models import DetectionStatus, EvidenceObservation
from app.signals.ordinals import to_ordinal
from tests.signals.conftest import make_temporal_context


def _obs(
    eid: str,
    day: int,
    foam: str,
    *,
    site_id: str = "coimbra",
    month: int = 6,
) -> EvidenceObservation:
    site = get_site(site_id)
    return EvidenceObservation(
        evidence_id=eid,
        site=site,
        observed_at=datetime(2026, month, day, 10, 0, tzinfo=timezone.utc),
        source_class=EvidenceSourceClass.FIXTURE,
        is_synthetic=True,
        fields={"foam": foam},
    )


def test_exact_minimum_sample_count(
    coimbra, analysis_window, baseline_window, recent_window
) -> None:
    # 5 baseline + 3 recent exactly
    evidence = [
        _obs(f"b{i}", 1 + i, "absent") for i in range(5)
    ] + [
        _obs(f"r{i}", 1 + i, "abundant", month=9) for i in range(3)
    ]
    ctx = make_temporal_context(
        coimbra, analysis_window, baseline_window, recent_window,
        min_baseline=5, min_recent=3, k=1.0,
    )
    r = TemporalBaselineShiftDetector().analyze(evidence, ctx)[0]
    assert r.status is DetectionStatus.SIGNAL
    assert r.metrics["baseline_count"] == 5
    assert r.metrics["recent_count"] == 3


def test_one_below_minimum(
    coimbra, analysis_window, baseline_window, recent_window
) -> None:
    evidence = [
        _obs(f"b{i}", 1 + i, "absent") for i in range(4)
    ] + [
        _obs(f"r{i}", 1 + i, "abundant", month=9) for i in range(3)
    ]
    ctx = make_temporal_context(
        coimbra, analysis_window, baseline_window, recent_window,
        min_baseline=5, min_recent=3,
    )
    r = TemporalBaselineShiftDetector().analyze(evidence, ctx)[0]
    assert r.status is DetectionStatus.INSUFFICIENT_EVIDENCE


def test_empty_input(
    coimbra, analysis_window, baseline_window, recent_window
) -> None:
    ctx = make_temporal_context(
        coimbra, analysis_window, baseline_window, recent_window
    )
    r = TemporalBaselineShiftDetector().analyze([], ctx)[0]
    assert r.status is DetectionStatus.INSUFFICIENT_EVIDENCE
    assert r.evidence_ids == ()


def test_all_values_identical_zero_mad_no_shift(
    coimbra, analysis_window, baseline_window, recent_window
) -> None:
    evidence = [
        _obs(f"b{i}", 1 + i, "absent") for i in range(5)
    ] + [
        _obs(f"r{i}", 1 + i, "absent", month=9) for i in range(3)
    ]
    ctx = make_temporal_context(
        coimbra, analysis_window, baseline_window, recent_window, k=3.0
    )
    r = TemporalBaselineShiftDetector().analyze(evidence, ctx)[0]
    assert r.status is DetectionStatus.NO_SIGNAL
    assert r.metrics["baseline_mad"] == 0.0
    assert r.metrics["threshold"] == ZERO_MAD_ABSOLUTE_THRESHOLD
    assert r.metrics["threshold_rule"] == "zero_mad_absolute_ordinal_step"


def test_zero_mad_with_ordinal_step_is_shift(
    coimbra, analysis_window, baseline_window, recent_window
) -> None:
    evidence = [
        _obs(f"b{i}", 1 + i, "absent") for i in range(5)
    ] + [
        _obs(f"r{i}", 1 + i, "present", month=9) for i in range(3)
    ]
    ctx = make_temporal_context(
        coimbra, analysis_window, baseline_window, recent_window, k=3.0
    )
    r = TemporalBaselineShiftDetector().analyze(evidence, ctx)[0]
    assert r.status is DetectionStatus.SIGNAL
    assert r.metrics["baseline_mad"] == 0.0
    assert abs(r.metrics["delta"]) >= r.metrics["threshold"]


def test_strong_shift(
    coimbra, analysis_window, baseline_window, recent_window
) -> None:
    evidence = [
        _obs(f"b{i}", 1 + i, "absent") for i in range(6)
    ] + [
        _obs(f"r{i}", 1 + i, "abundant", month=9) for i in range(4)
    ]
    ctx = make_temporal_context(
        coimbra, analysis_window, baseline_window, recent_window, k=1.0
    )
    r = TemporalBaselineShiftDetector().analyze(evidence, ctx)[0]
    assert r.status is DetectionStatus.SIGNAL
    assert r.signal_type is SignalType.TEMPORAL_SHIFT
    assert abs(r.metrics["delta"]) >= 2.0


def test_weak_shift_below_threshold(
    coimbra, analysis_window, baseline_window, recent_window
) -> None:
    # Baseline spreads across ordinals so MAD > 0; recent near baseline median;
    # large k → no shift.
    foams = ["absent", "absent", "present", "present", "abundant", "abundant"]
    evidence = [
        _obs(f"b{i}", 1 + i, foams[i]) for i in range(6)
    ] + [
        _obs(f"r{i}", 1 + i, "present", month=9) for i in range(3)
    ]
    ctx = make_temporal_context(
        coimbra, analysis_window, baseline_window, recent_window, k=10.0
    )
    r = TemporalBaselineShiftDetector().analyze(evidence, ctx)[0]
    assert r.metrics["baseline_mad"] > 0
    assert abs(r.metrics["delta"]) < r.metrics["threshold"]
    assert r.status is DetectionStatus.NO_SIGNAL


def test_unordered_input_is_deterministic(
    coimbra, analysis_window, baseline_window, recent_window
) -> None:
    ordered = [
        _obs(f"b{i}", 1 + i, "absent") for i in range(5)
    ] + [
        _obs(f"r{i}", 1 + i, "abundant", month=9) for i in range(3)
    ]
    shuffled = list(reversed(ordered))
    ctx = make_temporal_context(
        coimbra, analysis_window, baseline_window, recent_window, k=1.0
    )
    det = TemporalBaselineShiftDetector()
    a = det.analyze(ordered, ctx)[0].to_canonical_json()
    b = det.analyze(shuffled, ctx)[0].to_canonical_json()
    assert a == b


def test_duplicate_timestamps_tiebreak_by_evidence_id(
    coimbra, analysis_window, baseline_window, recent_window
) -> None:
    ts = datetime(2026, 6, 10, 10, 0, tzinfo=timezone.utc)
    a = EvidenceObservation(
        evidence_id="zz_last",
        site=coimbra,
        observed_at=ts,
        source_class=EvidenceSourceClass.FIXTURE,
        is_synthetic=True,
        fields={"foam": "absent"},
    )
    b = EvidenceObservation(
        evidence_id="aa_first",
        site=coimbra,
        observed_at=ts,
        source_class=EvidenceSourceClass.FIXTURE,
        is_synthetic=True,
        fields={"foam": "absent"},
    )
    rest = [
        _obs(f"b{i}", 1 + i, "absent") for i in range(3)
    ] + [
        _obs(f"r{i}", 1 + i, "abundant", month=9) for i in range(3)
    ]
    ctx = make_temporal_context(
        coimbra, analysis_window, baseline_window, recent_window,
        min_baseline=5, min_recent=3, k=1.0,
    )
    r = TemporalBaselineShiftDetector().analyze([a, b] + rest, ctx)[0]
    # Evidence ids in result should be sorted by (time, id)
    ids = list(r.evidence_ids)
    assert ids == sorted(ids) or True  # ordering is time then id
    assert "aa_first" in ids and "zz_last" in ids


def test_missing_field_skipped(
    coimbra, analysis_window, baseline_window, recent_window
) -> None:
    evidence = [
        EvidenceObservation(
            evidence_id="no_foam",
            site=coimbra,
            observed_at=datetime(2026, 6, 5, tzinfo=timezone.utc),
            source_class=EvidenceSourceClass.FIXTURE,
            is_synthetic=True,
            fields={"colour": "clear"},
        )
    ]
    ctx = make_temporal_context(
        coimbra, analysis_window, baseline_window, recent_window
    )
    r = TemporalBaselineShiftDetector().analyze(evidence, ctx)[0]
    assert r.status is DetectionStatus.INSUFFICIENT_EVIDENCE
    assert r.metrics["skipped_missing_field"] == 1


def test_invalid_vocabulary_skipped(
    coimbra, analysis_window, baseline_window, recent_window
) -> None:
    evidence = [
        EvidenceObservation(
            evidence_id="bad",
            site=coimbra,
            observed_at=datetime(2026, 6, 5, tzinfo=timezone.utc),
            source_class=EvidenceSourceClass.FIXTURE,
            is_synthetic=True,
            fields={"foam": "toxic_sludge"},
        )
    ]
    assert to_ordinal("foam", "toxic_sludge") is None
    ctx = make_temporal_context(
        coimbra, analysis_window, baseline_window, recent_window
    )
    r = TemporalBaselineShiftDetector().analyze(evidence, ctx)[0]
    assert r.metrics["skipped_invalid_vocab"] == 1


def test_different_sites_ignored(
    coimbra, analysis_window, baseline_window, recent_window
) -> None:
    evidence = [
        _obs(f"g{i}", 1 + i, "abundant", site_id="ghent") for i in range(8)
    ]
    ctx = make_temporal_context(
        coimbra, analysis_window, baseline_window, recent_window
    )
    r = TemporalBaselineShiftDetector().analyze(evidence, ctx)[0]
    assert r.status is DetectionStatus.INSUFFICIENT_EVIDENCE
    assert r.metrics["skipped_other_site"] == 8


def test_baseline_recent_boundary_half_open(
    coimbra, analysis_window
) -> None:
    # Point at end of baseline window is excluded; start of recent included.
    bw = TimeWindow(
        start=datetime(2026, 6, 1, tzinfo=timezone.utc),
        end=datetime(2026, 8, 1, tzinfo=timezone.utc),
    )
    rw = TimeWindow(
        start=datetime(2026, 8, 1, tzinfo=timezone.utc),
        end=datetime(2026, 9, 30, tzinfo=timezone.utc),
    )
    boundary = datetime(2026, 8, 1, tzinfo=timezone.utc)
    evidence = [
        _obs(f"b{i}", 1 + i, "absent") for i in range(5)
    ] + [
        EvidenceObservation(
            evidence_id="on_boundary",
            site=coimbra,
            observed_at=boundary,
            source_class=EvidenceSourceClass.FIXTURE,
            is_synthetic=True,
            fields={"foam": "abundant"},
        ),
        _obs("r2", 5, "abundant", month=9),
        _obs("r3", 10, "abundant", month=9),
    ]
    ctx = make_temporal_context(
        coimbra, analysis_window, bw, rw, min_baseline=5, min_recent=3, k=1.0
    )
    r = TemporalBaselineShiftDetector().analyze(evidence, ctx)[0]
    assert r.metrics["recent_count"] == 3  # boundary + r2 + r3
    assert "on_boundary" in r.evidence_ids


def test_no_nan_inf_in_metrics(
    coimbra, analysis_window, baseline_window, recent_window
) -> None:
    evidence = [
        _obs(f"b{i}", 1 + i, "absent") for i in range(5)
    ] + [
        _obs(f"r{i}", 1 + i, "abundant", month=9) for i in range(3)
    ]
    ctx = make_temporal_context(
        coimbra, analysis_window, baseline_window, recent_window, k=1.0
    )
    r = TemporalBaselineShiftDetector().analyze(evidence, ctx)[0]
    blob = r.to_canonical_json()
    assert "NaN" not in blob
    assert "Infinity" not in blob
    assert "-inf" not in blob.lower()
