"""P1.6 — vocabulary canonicalization for detectors; originals retained."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.demo.fixture_loader import load_fixture
from app.domain.enums import WorkflowState
from app.domain.evidence.enums import RelationType
from app.fhir.exporter import export_bundle_with_meta
from app.signals.vocabulary import (
    VOCABULARY_CANONICALIZATION_VERSION,
    canonical_value,
    canonicalize_fields,
)
from tests.application.aquasignal.conftest import (
    build_packet,
    make_analysis_params,
    persist_packet,
)

T0 = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    "field, raw, expected",
    [
        ("foam", "none", "absent"),
        ("foam", " None ", "absent"),
        ("foam", "absent", "absent"),
        ("foam", "abundant", "abundant"),
        ("colour", "Gray", "grey"),
        ("macrophytes_non_native", "yes", "true"),
        ("riparian_non_native", "0", "false"),
        ("riparian_non_native", True, "true"),
        ("smell", "none", "none"),
        ("riparian_vegetation", "0-25", "0-25"),
        ("riparian_vegetation", "0-20-percent", "0-20-percent"),
    ],
)
def test_canonical_value(field, raw, expected) -> None:
    assert canonical_value(field, raw) == expected


def test_canonicalize_is_deterministic_and_pure() -> None:
    fields = {"foam": "none", "colour": "gray"}
    assert canonicalize_fields(fields) == canonicalize_fields(dict(fields))
    assert fields == {"foam": "none", "colour": "gray"}


def test_absent_vs_none_is_not_a_contradiction(
    analysis, observation, coimbra, citizen, system, uow_factory
) -> None:
    ids = []
    for d, foam in ((0, "absent"), (1, "none")):
        packet = build_packet(
            site=coimbra, citizen=citizen, system=system,
            state=WorkflowState.FINALIZED, effective_at=T0 + timedelta(days=d), foam=foam,
        )
        ids.append(persist_packet(observation, packet))

    outcome = analysis.analyze_finalized_for_site(site=coimbra)

    assert not any(r.relation_type is RelationType.CONFLICTS for r in outcome.relations)
    assert any(r.relation_type is RelationType.SUPPORTS for r in outcome.relations)
    assert outcome.snapshot.source_manifest["vocabulary_version"] == VOCABULARY_CANONICALIZATION_VERSION
    # Originals retained for provenance and FHIR.
    with uow_factory() as uow:
        assert uow.evidence_items.require(ids[1]).fields["foam"] == "none"
    packet = observation.get(ids[1]).packet
    assert packet.fields["foam"].value == "none"
    assert export_bundle_with_meta(packet).bundle_hash


def test_fixture_b_no_longer_conflicts_through_service(
    analysis, coimbra, analysis_window, baseline_window, recent_window
) -> None:
    params = make_analysis_params(coimbra, analysis_window, baseline_window, recent_window)
    outcome = analysis.analyze(
        site=coimbra,
        time_window=analysis_window,
        fixture_observations=load_fixture("B_stable_control"),
        params=params,
    )
    assert not any(r.relation_type is RelationType.CONFLICTS for r in outcome.relations)
