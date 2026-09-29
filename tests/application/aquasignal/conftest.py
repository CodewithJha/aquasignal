"""AquaSignal Phase A4 — application orchestration fixtures."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.application.analysis_service import AnalysisService
from app.application.investigation_service import InvestigationService
from app.application.service import ObservationService
from app.domain.enums import ActorType, WorkflowState
from app.domain.packet import ObservationPacket
from app.domain.signal.value_objects import TimeWindow
from app.domain.sites import get_site
from app.domain.value_objects import Actor, FieldValue
from app.persistence.config import DatabaseSettings
from app.persistence.factory import open_unit_of_work
from app.signals.engine import SignalEngine
from app.signals.params import ContradictionParams, TemporalBaselineParams
from tests.db import make_settings


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test_aquasignal_a4.sqlite3"


@pytest.fixture
def settings(db_path: Path) -> DatabaseSettings:
    return make_settings(db_path)


@pytest.fixture
def uow_factory(settings: DatabaseSettings):
    _conn, factory = open_unit_of_work(settings)
    return factory


@pytest.fixture
def observation(uow_factory) -> ObservationService:
    return ObservationService(uow_factory)


@pytest.fixture
def analysis(uow_factory) -> AnalysisService:
    return AnalysisService(uow_factory, signal_engine=SignalEngine())


@pytest.fixture
def investigation(uow_factory) -> InvestigationService:
    return InvestigationService(uow_factory)


@pytest.fixture
def coimbra():
    return get_site("coimbra")


@pytest.fixture
def citizen() -> Actor:
    return Actor(ActorType.CITIZEN, "citizen-a4")


@pytest.fixture
def system() -> Actor:
    return Actor(ActorType.SYSTEM, "system-a4")


@pytest.fixture
def reviewer() -> Actor:
    return Actor(ActorType.REVIEWER, "reviewer-a4")


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


def make_analysis_params(
    coimbra,
    analysis_window: TimeWindow,
    baseline_window: TimeWindow,
    recent_window: TimeWindow,
    *,
    k: float = 1.0,
) -> dict:
    temporal = TemporalBaselineParams(
        field_code="foam",
        baseline_window=baseline_window,
        recent_window=recent_window,
        minimum_baseline_samples=5,
        minimum_recent_samples=3,
        threshold_multiplier=k,
    )
    contra = ContradictionParams()
    return {
        "temporal_baseline_shift": temporal,
        "cross_observation_contradiction": contra,
    }


def build_packet(
    *,
    site,
    citizen: Actor,
    system: Actor,
    state: WorkflowState,
    effective_at: datetime | None = None,
    foam: str = "present",
    packet_id: str | None = None,
) -> ObservationPacket:
    packet = ObservationPacket.create(
        site,
        author_actor_id=citizen.actor_id,
        submitter_display="A4 Citizen",
        effective_at=effective_at
        or datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc),
        packet_id=packet_id,
    )
    for code, value in (
        ("foam", foam),
        ("colour", "clear"),
        ("smell", "none"),
    ):
        packet.set_field(FieldValue(code=code, value=value), actor=citizen)

    if state is WorkflowState.RECEIVED:
        return packet

    packet.apply_flags([], actor=system)
    if state is WorkflowState.FLAGGED:
        return packet

    packet.mark_awaiting_confirm(actor=system)
    if state is WorkflowState.AWAITING_CONFIRM:
        return packet

    packet.confirm(actor=citizen)
    if state is WorkflowState.CONFIRMED:
        return packet

    if state is WorkflowState.FINALIZED:
        packet.finalize(actor=system)
        return packet

    raise AssertionError(f"unsupported helper state {state}")


def persist_packet(observation: ObservationService, packet: ObservationPacket) -> str:
    observation.persist_new(packet)
    return packet.packet_id
