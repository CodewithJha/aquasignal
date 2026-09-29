"""Fixtures for AquaSignal Phase A1 domain tests."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.domain.enums import ActorType
from app.domain.value_objects import Actor, SiteRef


@pytest.fixture
def coimbra_site() -> SiteRef:
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
def citizen() -> Actor:
    return Actor(ActorType.CITIZEN, "citizen-1")


@pytest.fixture
def system() -> Actor:
    return Actor(ActorType.SYSTEM, "signal-engine")


@pytest.fixture
def ai_actor() -> Actor:
    return Actor(ActorType.AI_PROVIDER, "null-copilot")


@pytest.fixture
def window():
    from app.domain.signal.value_objects import TimeWindow

    return TimeWindow(
        start=datetime(2026, 9, 1, tzinfo=timezone.utc),
        end=datetime(2026, 9, 22, tzinfo=timezone.utc),
    )
