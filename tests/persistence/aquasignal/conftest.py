"""AquaSignal Phase A2 — persistence integration fixtures."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.domain.enums import ActorType
from app.domain.evidence.enums import EvidenceSourceClass, RelationType
from app.domain.evidence.item import EvidenceItem
from app.domain.evidence.relation import EvidenceRelation
from app.domain.evidence.snapshot import EvidenceSnapshot
from app.domain.investigation.analysis_run import AnalysisRun
from app.domain.investigation.case import InvestigationCase
from app.domain.investigation.decision import HumanDecision
from app.domain.investigation.enums import DecisionCode
from app.domain.signal.enums import SignalType
from app.domain.signal.environmental import EnvironmentalSignal
from app.domain.signal.value_objects import DetectorId, DetectorVersion, TimeWindow
from app.domain.value_objects import Actor, SiteRef
from app.persistence.config import DatabaseSettings
from app.persistence.factory import open_unit_of_work
from tests.db import make_settings


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test_aquasignal_a2.sqlite3"


@pytest.fixture
def settings(db_path: Path) -> DatabaseSettings:
    return make_settings(db_path)


@pytest.fixture
def uow_factory(settings: DatabaseSettings):
    _conn, factory = open_unit_of_work(settings)
    return factory


@pytest.fixture
def coimbra() -> SiteRef:
    return SiteRef(
        site_id="coimbra",
        city="Coimbra",
        display_name="Coimbra, Portugal",
        lat=40.2033,
        lon=-8.4103,
    )


@pytest.fixture
def reviewer() -> Actor:
    return Actor(ActorType.REVIEWER, "reviewer-1")


@pytest.fixture
def window() -> TimeWindow:
    return TimeWindow(
        start=datetime(2026, 9, 1, tzinfo=timezone.utc),
        end=datetime(2026, 9, 22, tzinfo=timezone.utc),
    )


@pytest.fixture
def observed_at() -> datetime:
    return datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)


def make_packet_evidence(site: SiteRef, observed_at: datetime, *, eid: str) -> EvidenceItem:
    return EvidenceItem.create(
        evidence_id=eid,
        source_class=EvidenceSourceClass.CONFIRMGATE_PACKET,
        site=site,
        observed_at=observed_at,
        payload_ref=f"packet:{eid}",
        content_hash=f"hash-{eid}",
        license_tag="oah-demo",
        is_synthetic=False,
    )


def make_fixture_evidence(site: SiteRef, observed_at: datetime, *, eid: str) -> EvidenceItem:
    return EvidenceItem.create(
        evidence_id=eid,
        source_class=EvidenceSourceClass.FIXTURE,
        site=site,
        observed_at=observed_at,
        payload_ref=f"fixture:{eid}",
        content_hash=f"hash-{eid}",
        license_tag="synthetic-fixture",
        is_synthetic=True,
    )


def make_snapshot(evidence_ids: tuple[str, ...], *, sid: str = "snap_a2demo") -> EvidenceSnapshot:
    return EvidenceSnapshot.create(
        snapshot_id=sid,
        ordered_evidence_ids=evidence_ids,
        source_manifest={"source": "a2-test", "n": len(evidence_ids)},
        created_at=datetime(2026, 9, 15, tzinfo=timezone.utc),
    )


def make_run(
    *,
    snapshot_hash: str,
    run_id: str = "run_a2demo",
    site_id: str = "coimbra",
    window: TimeWindow | None = None,
) -> AnalysisRun:
    tw = window or TimeWindow(
        start=datetime(2026, 9, 1, tzinfo=timezone.utc),
        end=datetime(2026, 9, 22, tzinfo=timezone.utc),
    )
    return AnalysisRun.start(
        run_id=run_id,
        snapshot_hash=snapshot_hash,
        detector_set_version="detectors@0.1.0",
        parameters_hash="params-abc",
        site_id=site_id,
        time_window=tw,
        started_at=datetime(2026, 9, 15, 1, 0, tzinfo=timezone.utc),
    )


def make_signal(
    *,
    site: SiteRef,
    window: TimeWindow,
    run_id: str,
    evidence_ids: tuple[str, ...],
    signal_id: str = "sig_a2demo",
) -> EnvironmentalSignal:
    return EnvironmentalSignal.create(
        signal_id=signal_id,
        detector_id=DetectorId("temporal_baseline_shift"),
        detector_version=DetectorVersion("1.0.0"),
        signal_type=SignalType.TEMPORAL_SHIFT,
        site=site,
        time_window=window,
        summary="Possible temporal shift in foam reports (hypothesis, not diagnosis).",
        metrics={"delta": 0.4, "n_before": 2, "n_after": 2},
        evidence_ids=evidence_ids,
        analysis_run_id=run_id,
        explanation={"rule": "abs_delta_gt_threshold", "threshold": 0.3},
    )


def make_relation(*, run_id: str, left: str, right: str, rid: str = "rel_a2demo") -> EvidenceRelation:
    return EvidenceRelation.create(
        relation_id=rid,
        relation_type=RelationType.CONFLICTS,
        left_ref=left,
        right_ref=right,
        analysis_run_id=run_id,
        rationale_code="protocol_conflict",
        message="Foam present vs absent within window",
    )


def make_case(
    *,
    site: SiteRef,
    window: TimeWindow,
    run_id: str,
    signal_ids: tuple[str, ...],
    reviewer: Actor,
    case_id: str = "case_a2demo",
) -> InvestigationCase:
    return InvestigationCase.open(
        case_id=case_id,
        site=site,
        window=window,
        analysis_run_id=run_id,
        signal_ids=signal_ids,
        reproducibility_ref="run_a2demo@snap",
        opened_by=reviewer,
        opened_at=datetime(2026, 9, 15, 2, 0, tzinfo=timezone.utc),
    )


def make_decision(
    *,
    case_id: str,
    actor: Actor,
    signal_ids: tuple[str, ...] = (),
    decision_id: str = "dec_a2demo",
) -> HumanDecision:
    return HumanDecision.create(
        decision_id=decision_id,
        case_id=case_id,
        actor=actor,
        decision_code=DecisionCode.NOTE,
        rationale="Logged for reviewer follow-up; not a pollution finding.",
        linked_signal_ids=signal_ids,
        decided_at=datetime(2026, 9, 15, 3, 0, tzinfo=timezone.utc),
    )
