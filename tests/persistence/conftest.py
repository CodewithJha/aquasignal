"""Isolated temp SQLite fixtures for Phase 4 persistence tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.application.service import ObservationService
from app.domain.enums import ActorType
from app.domain.packet import ObservationPacket
from app.domain.value_objects import Actor, FieldValue, SiteRef
from app.persistence.config import DatabaseSettings
from app.persistence.factory import open_unit_of_work
from tests.db import make_settings


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test_confirmgate.sqlite3"


@pytest.fixture
def settings(db_path: Path) -> DatabaseSettings:
    return make_settings(db_path)


@pytest.fixture
def uow_factory(settings: DatabaseSettings):
    _conn, factory = open_unit_of_work(settings)
    return factory


@pytest.fixture
def service(uow_factory) -> ObservationService:
    return ObservationService(uow_factory)


@pytest.fixture
def coimbra() -> SiteRef:
    return SiteRef(
        site_id="coimbra",
        city="Coimbra",
        display_name="Coimbra, Portugal",
    )


@pytest.fixture
def citizen() -> Actor:
    return Actor(ActorType.CITIZEN, "citizen-1")


@pytest.fixture
def system() -> Actor:
    return Actor(ActorType.SYSTEM, "flag-engine")


@pytest.fixture
def fresh_packet(coimbra: SiteRef, citizen: Actor) -> ObservationPacket:
    return ObservationPacket.create(
        coimbra,
        author_actor_id=citizen.actor_id,
        submitter_display="Tester",
    )


def foam(citizen: Actor | None = None) -> FieldValue:
    return FieldValue(code="foam", value="present")
