"""Cross-observation contradiction — edge cases from A3 brief."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.domain.evidence.enums import EvidenceSourceClass, RelationType
from app.domain.sites import get_site
from app.domain.signal.enums import SignalType
from app.domain.signal.value_objects import TimeWindow
from app.signals.detectors.cross_observation_contradiction import (
    CrossObservationContradictionDetector,
)
from app.signals.models import DetectionStatus, EvidenceObservation
from tests.signals.conftest import make_contradiction_context


def _obs(
    eid: str,
    when: datetime,
    fields: dict[str, str],
    *,
    site_id: str = "coimbra",
) -> EvidenceObservation:
    return EvidenceObservation(
        evidence_id=eid,
        site=get_site(site_id),
        observed_at=when,
        source_class=EvidenceSourceClass.FIXTURE,
        is_synthetic=True,
        fields=fields,
    )


T0 = datetime(2026, 9, 10, 10, 0, tzinfo=timezone.utc)
# Same visit: inside the 24 h comparison window, outside the 10 min duplicate delta.
T1 = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)


def test_one_observation_insufficient(coimbra, analysis_window) -> None:
    evidence = [_obs("only", T0, {"foam": "present"})]
    r = CrossObservationContradictionDetector().analyze(
        evidence, make_contradiction_context(coimbra, analysis_window)
    )[0]
    assert r.status is DetectionStatus.INSUFFICIENT_EVIDENCE
    assert r.signal_type is SignalType.INSUFFICIENT_EVIDENCE
    assert r.relations == ()


def test_two_conflicting(coimbra, analysis_window) -> None:
    evidence = [
        _obs("b", T0, {"foam": "absent"}),
        _obs("a", T1, {"foam": "present"}),
    ]
    r = CrossObservationContradictionDetector().analyze(
        evidence, make_contradiction_context(coimbra, analysis_window)
    )[0]
    assert r.status is DetectionStatus.SIGNAL
    assert r.signal_type is SignalType.CONTRADICTION
    foam = [x for x in r.relations if x.field_code == "foam"][0]
    assert foam.relation_type is RelationType.CONFLICTS
    assert foam.left_ref == "a"  # canonical min id
    assert foam.right_ref == "b"


def test_duplicate_observations(coimbra, analysis_window) -> None:
    evidence = [
        _obs("a", T0, {"foam": "present"}),
        _obs("b", T0, {"foam": "present"}),
    ]
    r = CrossObservationContradictionDetector().analyze(
        evidence, make_contradiction_context(coimbra, analysis_window)
    )[0]
    assert r.status is DetectionStatus.NO_SIGNAL
    foam = [x for x in r.relations if x.field_code == "foam"][0]
    assert foam.relation_type is RelationType.DUPLICATES


def test_supporting_observations(coimbra, analysis_window) -> None:
    evidence = [
        _obs("a", T0, {"foam": "present"}),
        _obs("b", T1, {"foam": "present"}),
    ]
    r = CrossObservationContradictionDetector().analyze(
        evidence, make_contradiction_context(coimbra, analysis_window)
    )[0]
    foam = [x for x in r.relations if x.field_code == "foam"][0]
    assert foam.relation_type is RelationType.SUPPORTS


def test_same_timestamp_conflict(coimbra, analysis_window) -> None:
    evidence = [
        _obs("a", T0, {"foam": "present"}),
        _obs("b", T0, {"foam": "absent"}),
    ]
    r = CrossObservationContradictionDetector().analyze(
        evidence, make_contradiction_context(coimbra, analysis_window)
    )[0]
    assert r.status is DetectionStatus.SIGNAL
    foam = [x for x in r.relations if x.field_code == "foam"][0]
    assert foam.relation_type is RelationType.CONFLICTS


def test_different_timestamps(coimbra, analysis_window) -> None:
    evidence = [
        _obs("a", T0, {"foam": "present"}),
        _obs("b", T1 + timedelta(days=2), {"foam": "absent"}),
    ]
    r = CrossObservationContradictionDetector().analyze(
        evidence, make_contradiction_context(coimbra, analysis_window)
    )[0]
    # Separate visits: outside the comparison window → no relation at all.
    assert r.status is DetectionStatus.NO_SIGNAL
    assert r.relations == ()


def test_different_sites_not_compared(coimbra, analysis_window) -> None:
    evidence = [
        _obs("a", T0, {"foam": "present"}, site_id="coimbra"),
        _obs("b", T1, {"foam": "absent"}, site_id="ghent"),
    ]
    r = CrossObservationContradictionDetector().analyze(
        evidence, make_contradiction_context(coimbra, analysis_window)
    )[0]
    assert r.status is DetectionStatus.INSUFFICIENT_EVIDENCE


def test_incompatible_fields_not_paired(coimbra, analysis_window) -> None:
    evidence = [
        _obs("a", T0, {"foam": "present"}),
        _obs("b", T1, {"macrophytes": "a"}),
    ]
    # Restrict to foam only — second obs has no foam → insufficient or no foam pairs
    ctx = make_contradiction_context(
        coimbra, analysis_window, field_codes=("foam",)
    )
    r = CrossObservationContradictionDetector().analyze(evidence, ctx)[0]
    assert r.status is DetectionStatus.INSUFFICIENT_EVIDENCE


def test_invalid_vocabulary_ignored(coimbra, analysis_window) -> None:
    evidence = [
        _obs("a", T0, {"foam": "present"}),
        _obs("b", T1, {"foam": "not_a_real_value"}),
    ]
    r = CrossObservationContradictionDetector().analyze(
        evidence, make_contradiction_context(coimbra, analysis_window)
    )[0]
    # Only one valid foam holder → insufficient
    assert r.status is DetectionStatus.INSUFFICIENT_EVIDENCE


def test_multiple_conflicting_observations(coimbra, analysis_window) -> None:
    evidence = [
        _obs("a", T0, {"foam": "absent"}),
        _obs("b", T1, {"foam": "present"}),
        _obs("c", T1 + timedelta(hours=1), {"foam": "abundant"}),
    ]
    r = CrossObservationContradictionDetector().analyze(
        evidence, make_contradiction_context(coimbra, analysis_window)
    )[0]
    foam_conflicts = [
        x
        for x in r.relations
        if x.field_code == "foam" and x.relation_type is RelationType.CONFLICTS
    ]
    # C(3,2) = 3 pairs, all conflicting values
    assert len(foam_conflicts) == 3
    # Never emit reverse duplicates of same pair
    pairs = {(x.left_ref, x.right_ref) for x in foam_conflicts}
    assert pairs == {("a", "b"), ("a", "c"), ("b", "c")}
    for left, right in pairs:
        assert left < right


def test_deterministic_pair_ordering(coimbra, analysis_window) -> None:
    evidence = [
        _obs("z_high", T0, {"foam": "present"}),
        _obs("a_low", T1, {"foam": "absent"}),
    ]
    det = CrossObservationContradictionDetector()
    ctx = make_contradiction_context(coimbra, analysis_window)
    r1 = det.analyze(evidence, ctx)[0]
    r2 = det.analyze(list(reversed(evidence)), ctx)[0]
    assert r1.to_canonical_json() == r2.to_canonical_json()
    foam = [x for x in r1.relations if x.field_code == "foam"][0]
    assert foam.left_ref == "a_low"
    assert foam.right_ref == "z_high"


def test_outside_time_window_excluded(coimbra) -> None:
    narrow = TimeWindow(
        start=datetime(2026, 9, 1, tzinfo=timezone.utc),
        end=datetime(2026, 9, 11, tzinfo=timezone.utc),
    )
    evidence = [
        _obs("a", T0, {"foam": "present"}),
        _obs("b", datetime(2026, 10, 1, tzinfo=timezone.utc), {"foam": "absent"}),
    ]
    r = CrossObservationContradictionDetector().analyze(
        evidence, make_contradiction_context(coimbra, narrow)
    )[0]
    assert r.status is DetectionStatus.INSUFFICIENT_EVIDENCE


def test_never_emit_a_conflicts_b_and_b_conflicts_a(
    coimbra, analysis_window
) -> None:
    evidence = [
        _obs("x", T0, {"foam": "present", "colour": "brown"}),
        _obs("y", T1, {"foam": "absent", "colour": "clear"}),
    ]
    r = CrossObservationContradictionDetector().analyze(
        evidence, make_contradiction_context(coimbra, analysis_window)
    )[0]
    keys = [
        (rel.field_code, rel.left_ref, rel.right_ref, rel.relation_type.value)
        for rel in r.relations
    ]
    assert len(keys) == len(set(keys))
    for field, left, right, _ in keys:
        assert left < right or left == right  # should be strict < for distinct ids
        assert left <= right
