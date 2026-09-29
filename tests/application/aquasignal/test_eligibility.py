"""A4 — FINALIZED eligibility gate (domain/application, not UI)."""

from __future__ import annotations

import pytest

from app.application.errors import EvidenceNotEligible
from app.application.evidence_gate import require_finalized_packet, require_labelled_fixture
from app.application.evidence_mapping import packet_to_observation
from app.domain.enums import WorkflowState
from app.domain.evidence.enums import EvidenceSourceClass
from app.signals.models import EvidenceObservation
from tests.application.aquasignal.conftest import build_packet, persist_packet
from tests.signals.fixture_loader import load_fixture


@pytest.mark.parametrize(
    "state",
    [
        WorkflowState.RECEIVED,
        WorkflowState.FLAGGED,
        WorkflowState.AWAITING_CONFIRM,
        WorkflowState.CONFIRMED,
    ],
)
def test_draft_packets_rejected_as_evidence(
    analysis,
    observation,
    coimbra,
    citizen,
    system,
    analysis_window,
    baseline_window,
    recent_window,
    state: WorkflowState,
) -> None:
    packet = build_packet(site=coimbra, citizen=citizen, system=system, state=state)
    pid = persist_packet(observation, packet)
    from tests.application.aquasignal.conftest import make_analysis_params

    params = make_analysis_params(
        coimbra, analysis_window, baseline_window, recent_window
    )
    with pytest.raises(EvidenceNotEligible, match="FINALIZED"):
        analysis.analyze(
            site=coimbra,
            time_window=analysis_window,
            packet_ids=[pid],
            params=params,
        )


def test_finalized_packet_accepted_as_observation(
    coimbra, citizen, system
) -> None:
    packet = build_packet(
        site=coimbra,
        citizen=citizen,
        system=system,
        state=WorkflowState.FINALIZED,
    )
    require_finalized_packet(packet)
    obs = packet_to_observation(packet)
    assert obs.source_class is EvidenceSourceClass.CONFIRMGATE_PACKET
    assert obs.is_synthetic is False
    assert obs.fields["foam"] == "present"


def test_labelled_fixtures_accepted(analysis, coimbra, analysis_window, baseline_window, recent_window) -> None:
    from tests.application.aquasignal.conftest import make_analysis_params

    fixtures = load_fixture("C_contradiction")
    for f in fixtures:
        require_labelled_fixture(f)
    params = make_analysis_params(
        coimbra, analysis_window, baseline_window, recent_window
    )
    outcome = analysis.analyze(
        site=coimbra,
        time_window=analysis_window,
        fixture_observations=fixtures,
        params=params,
    )
    assert outcome.run.status.value == "SUCCEEDED"
    assert len(outcome.observations) == 2


def test_unlabelled_fixture_refused(coimbra) -> None:
    from datetime import datetime, timezone

    bad = EvidenceObservation(
        evidence_id="bad_fx",
        site=coimbra,
        observed_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        source_class=EvidenceSourceClass.FIXTURE,
        is_synthetic=False,
        fields={"foam": "present"},
    )
    with pytest.raises(EvidenceNotEligible, match="is_synthetic"):
        require_labelled_fixture(bad)
