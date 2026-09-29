"""Golden tests for AquaSignal fixtures A–E."""

from __future__ import annotations

from app.domain.evidence.enums import RelationType
from app.domain.signal.enums import SignalType
from app.signals.detectors.cross_observation_contradiction import (
    CrossObservationContradictionDetector,
)
from app.signals.detectors.temporal_baseline_shift import TemporalBaselineShiftDetector
from app.signals.models import DetectionStatus
from tests.signals.conftest import make_contradiction_context, make_temporal_context
from tests.signals.fixture_loader import load_fixture


def test_fixture_a_temporal_shift_golden(
    coimbra, analysis_window, baseline_window, recent_window
) -> None:
    evidence = load_fixture("A_temporal_shift")
    assert all(e.is_synthetic and e.source_class.value == "fixture" for e in evidence)
    ctx = make_temporal_context(
        coimbra, analysis_window, baseline_window, recent_window, k=1.0
    )
    results = TemporalBaselineShiftDetector().analyze(evidence, ctx)
    assert len(results) == 1
    r = results[0]
    assert r.status is DetectionStatus.SIGNAL
    assert r.signal_type is SignalType.TEMPORAL_SHIFT
    assert r.detector_id.value == "temporal_baseline_shift"
    assert r.detector_version.value == "v1"
    assert r.metrics["field_code"] == "foam"
    assert r.metrics["baseline_median"] == 0.0
    assert r.metrics["recent_median"] >= 1.5
    assert r.metrics["baseline_count"] == 8
    assert r.metrics["recent_count"] == 4
    assert abs(r.metrics["delta"]) >= r.metrics["threshold"]
    assert "fix_a_01" in r.evidence_ids
    assert "fix_a_r1" in r.evidence_ids
    assert "pollution" not in r.summary.lower()
    assert "pollution" not in str(r.explanation).lower()
    assert "threshold" in r.explanation


def test_fixture_b_stable_control_golden(
    coimbra, analysis_window, baseline_window, recent_window
) -> None:
    evidence = load_fixture("B_stable_control")
    ctx = make_temporal_context(
        coimbra, analysis_window, baseline_window, recent_window, k=3.0
    )
    results = TemporalBaselineShiftDetector().analyze(evidence, ctx)
    r = results[0]
    assert r.status is DetectionStatus.NO_SIGNAL
    assert r.signal_type is None
    assert r.detector_id.value == "temporal_baseline_shift"
    assert r.detector_version.value == "v1"
    assert r.metrics["baseline_median"] == 0.0
    assert r.metrics["recent_median"] == 0.0
    assert r.metrics["delta"] == 0.0
    assert "no meaningful temporal shift" in r.summary.lower()


def test_fixture_c_contradiction_golden(coimbra, analysis_window) -> None:
    evidence = load_fixture("C_contradiction")
    ctx = make_contradiction_context(coimbra, analysis_window)
    results = CrossObservationContradictionDetector().analyze(evidence, ctx)
    r = results[0]
    assert r.status is DetectionStatus.SIGNAL
    assert r.signal_type is SignalType.CONTRADICTION
    assert r.detector_id.value == "cross_observation_contradiction"
    assert r.detector_version.value == "v2"
    assert r.metrics["conflict_count"] >= 1
    assert r.metrics["conflicting_pair_count"] == 1
    assert r.metrics["pairs_compared"] == 1
    foam_conflicts = [
        rel
        for rel in r.relations
        if rel.field_code == "foam" and rel.relation_type is RelationType.CONFLICTS
    ]
    assert len(foam_conflicts) == 1
    rel = foam_conflicts[0]
    assert rel.left_ref == "fix_c_hi"
    assert rel.right_ref == "fix_c_lo"
    assert {rel.value_left, rel.value_right} == {"present", "absent"}
    assert "pollution" not in rel.message.lower()
    assert "fix_c_hi" in r.evidence_ids and "fix_c_lo" in r.evidence_ids


def test_fixture_d_duplicate_support_golden(coimbra, analysis_window) -> None:
    evidence = load_fixture("D_duplicate_support")
    ctx = make_contradiction_context(coimbra, analysis_window)
    results = CrossObservationContradictionDetector().analyze(evidence, ctx)
    r = results[0]
    assert r.status is DetectionStatus.NO_SIGNAL
    assert r.signal_type is None
    assert r.metrics["conflict_count"] == 0
    types = {rel.relation_type for rel in r.relations if rel.field_code == "foam"}
    assert RelationType.CONFLICTS not in types
    assert types == {RelationType.DUPLICATES}
    # Same-timestamp identical pair → duplicates on every shared field, never supports.
    dup = [rel for rel in r.relations if rel.relation_type is RelationType.DUPLICATES]
    assert {(d.field_code, d.left_ref, d.right_ref) for d in dup} == {
        ("foam", "fix_d_a", "fix_d_b"),
        ("macrophytes", "fix_d_a", "fix_d_b"),
    }
    # fix_d_c is four days later: outside the 24 h comparison window → no relation.
    assert all("fix_d_c" not in (rel.left_ref, rel.right_ref) for rel in r.relations)
    assert r.metrics["duplicate_pair_count"] == 1
    assert r.metrics["pairs_compared"] == 1
    assert r.metrics["pairs_outside_comparison_window"] == 2


def test_fixture_e_insufficient_golden(
    coimbra, analysis_window, baseline_window, recent_window
) -> None:
    evidence = load_fixture("E_insufficient")
    ctx = make_temporal_context(
        coimbra, analysis_window, baseline_window, recent_window,
        min_baseline=5,
        min_recent=3,
    )
    results = TemporalBaselineShiftDetector().analyze(evidence, ctx)
    r = results[0]
    assert r.status is DetectionStatus.INSUFFICIENT_EVIDENCE
    assert r.signal_type is SignalType.INSUFFICIENT_EVIDENCE
    assert r.metrics["baseline_count"] == 2
    assert r.metrics["recent_count"] == 1
    assert "insufficient" in r.summary.lower()
