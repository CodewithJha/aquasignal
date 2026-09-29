"""cross_observation_contradiction v2 — comparison window + pair-level duplicates."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.application.params_hash import hash_analysis_parameters
from app.domain.evidence.enums import EvidenceSourceClass, RelationType
from app.domain.signal.enums import SignalType
from app.domain.sites import get_site
from app.signals.detectors.cross_observation_contradiction import (
    CrossObservationContradictionDetector,
)
from app.signals.models import DetectionStatus, EvidenceObservation
from app.signals.params import ContradictionParams
from tests.signals.conftest import make_contradiction_context

T0 = datetime(2026, 9, 10, 9, 0, tzinfo=timezone.utc)


def _obs(eid: str, when: datetime, fields: dict[str, str]) -> EvidenceObservation:
    return EvidenceObservation(
        evidence_id=eid,
        site=get_site("coimbra"),
        observed_at=when,
        source_class=EvidenceSourceClass.FIXTURE,
        is_synthetic=True,
        fields=fields,
    )


def _run(evidence, coimbra, analysis_window, **kw):
    return CrossObservationContradictionDetector().analyze(
        evidence, make_contradiction_context(coimbra, analysis_window, **kw)
    )[0]


def test_defaults_are_24h_window_and_10min_duplicate() -> None:
    p = ContradictionParams()
    assert p.comparison_window == timedelta(hours=24)
    assert p.duplicate_max_delta == timedelta(minutes=10)
    assert p.to_dict()["comparison_window_seconds"] == 86400.0
    assert ContradictionParams.from_mapping(p.to_dict()) == p


def test_same_day_conflict_is_contradiction(coimbra, analysis_window) -> None:
    r = _run(
        [_obs("a", T0, {"foam": "present"}), _obs("b", T0 + timedelta(hours=3), {"foam": "absent"})],
        coimbra,
        analysis_window,
    )
    assert r.status is DetectionStatus.SIGNAL
    assert r.signal_type is SignalType.CONTRADICTION
    assert [x.relation_type for x in r.relations] == [RelationType.CONFLICTS]
    assert r.metrics["conflicting_pair_count"] == 1


@pytest.mark.parametrize("gap", [timedelta(days=2), timedelta(days=30)])
def test_separate_visits_with_different_values_produce_no_relation(
    coimbra, analysis_window, gap
) -> None:
    start = datetime(2026, 7, 1, 9, 0, tzinfo=timezone.utc)
    r = _run(
        [_obs("a", start, {"foam": "present"}), _obs("b", start + gap, {"foam": "absent"})],
        coimbra,
        analysis_window,
    )
    assert r.status is DetectionStatus.NO_SIGNAL
    assert r.signal_type is None
    assert r.relations == ()
    assert r.metrics["pairs_compared"] == 0
    assert r.metrics["pairs_outside_comparison_window"] == 1
    assert "no same-visit comparison" in r.summary.lower()


def test_identical_within_duplicate_delta_is_duplicate_only(
    coimbra, analysis_window
) -> None:
    fields = {"foam": "present", "colour": "clear"}
    r = _run(
        [_obs("a", T0, fields), _obs("b", T0 + timedelta(minutes=5), fields)],
        coimbra,
        analysis_window,
    )
    types = [x.relation_type for x in r.relations]
    assert types == [RelationType.DUPLICATES, RelationType.DUPLICATES]
    assert RelationType.SUPPORTS not in types
    assert r.metrics["duplicate_pair_count"] == 1
    assert r.metrics["agreeing_pair_count"] == 0
    assert r.metrics["support_count"] == 0


def test_identical_outside_duplicate_delta_but_in_window_is_support(
    coimbra, analysis_window
) -> None:
    r = _run(
        [_obs("a", T0, {"foam": "present"}), _obs("b", T0 + timedelta(minutes=11), {"foam": "present"})],
        coimbra,
        analysis_window,
    )
    assert [x.relation_type for x in r.relations] == [RelationType.SUPPORTS]
    assert r.metrics["agreeing_pair_count"] == 1
    assert r.metrics["duplicate_pair_count"] == 0


def test_partial_match_within_duplicate_delta_is_not_duplicate(
    coimbra, analysis_window
) -> None:
    """A near-simultaneous pair that disagrees on any field is not a duplicate."""
    r = _run(
        [
            _obs("a", T0, {"foam": "present", "colour": "clear"}),
            _obs("b", T0 + timedelta(minutes=2), {"foam": "absent", "colour": "clear"}),
        ],
        coimbra,
        analysis_window,
    )
    by_field = {x.field_code: x.relation_type for x in r.relations}
    assert by_field == {"colour": RelationType.SUPPORTS, "foam": RelationType.CONFLICTS}
    assert r.metrics["duplicate_pair_count"] == 0
    assert r.metrics["conflicting_pair_count"] == 1


def test_equal_in_window_supports_and_different_in_window_conflicts(
    coimbra, analysis_window
) -> None:
    r = _run(
        [
            _obs("a", T0, {"foam": "present", "smell": "none"}),
            _obs("b", T0 + timedelta(hours=20), {"foam": "absent", "smell": "none"}),
        ],
        coimbra,
        analysis_window,
    )
    by_field = {x.field_code: x.relation_type for x in r.relations}
    assert by_field == {"foam": RelationType.CONFLICTS, "smell": RelationType.SUPPORTS}


def test_window_boundary_is_inclusive(coimbra, analysis_window) -> None:
    inside = _run(
        [_obs("a", T0, {"foam": "present"}), _obs("b", T0 + timedelta(hours=24), {"foam": "absent"})],
        coimbra,
        analysis_window,
    )
    outside = _run(
        [
            _obs("a", T0, {"foam": "present"}),
            _obs("b", T0 + timedelta(hours=24, seconds=1), {"foam": "absent"}),
        ],
        coimbra,
        analysis_window,
    )
    assert inside.status is DetectionStatus.SIGNAL
    assert outside.relations == ()


def test_deterministic_across_input_order(coimbra, analysis_window) -> None:
    evidence = [
        _obs("c", T0 + timedelta(hours=2), {"foam": "absent"}),
        _obs("a", T0, {"foam": "present"}),
        _obs("b", T0 + timedelta(minutes=3), {"foam": "present"}),
        _obs("d", T0 + timedelta(days=9), {"foam": "abundant"}),
    ]
    det = CrossObservationContradictionDetector()
    ctx = make_contradiction_context(coimbra, analysis_window)
    first = det.analyze(evidence, ctx)[0].to_canonical_json()
    for _ in range(3):
        assert det.analyze(list(reversed(evidence)), ctx)[0].to_canonical_json() == first


def test_parameters_hash_changes_with_window() -> None:
    default = hash_analysis_parameters(
        {"cross_observation_contradiction": ContradictionParams()}
    )
    wider = hash_analysis_parameters(
        {
            "cross_observation_contradiction": ContradictionParams(
                comparison_window=timedelta(hours=48)
            )
        }
    )
    assert default != wider
    assert default == hash_analysis_parameters(
        {"cross_observation_contradiction": ContradictionParams()}
    )


def test_custom_window_is_honoured(coimbra, analysis_window) -> None:
    evidence = [
        _obs("a", T0, {"foam": "present"}),
        _obs("b", T0 + timedelta(days=2), {"foam": "absent"}),
    ]
    r = _run(evidence, coimbra, analysis_window, comparison_window=timedelta(days=3))
    assert r.status is DetectionStatus.SIGNAL


def test_invalid_params_rejected() -> None:
    with pytest.raises(ValueError):
        ContradictionParams(comparison_window=timedelta(hours=-1))
    with pytest.raises(ValueError):
        ContradictionParams(
            comparison_window=timedelta(minutes=5),
            duplicate_max_delta=timedelta(minutes=10),
        )


def test_insufficiency_rule_unchanged(coimbra, analysis_window) -> None:
    r = _run([_obs("a", T0, {"foam": "present"})], coimbra, analysis_window)
    assert r.status is DetectionStatus.INSUFFICIENT_EVIDENCE
    assert r.signal_type is SignalType.INSUFFICIENT_EVIDENCE
    assert r.relations == ()


def test_detector_reports_v2(coimbra, analysis_window) -> None:
    r = _run([_obs("a", T0, {"foam": "present"})], coimbra, analysis_window)
    assert r.detector_version.value == "v2"
