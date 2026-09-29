"""Shared fixtures for FlagEngine tests."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.domain.enums import ActorType
from app.domain.packet import ObservationPacket
from app.domain.value_objects import Actor, FieldValue, SiteRef
from app.flags.engine import DeterministicFlagEngine
from app.flags.ports import (
    DuplicateLookup,
    DuplicateMatch,
    MediaContext,
    MediaContextProvider,
)


@pytest.fixture
def coimbra_site() -> SiteRef:
    return SiteRef(
        site_id="coimbra",
        city="Coimbra",
        display_name="Coimbra, Portugal",
        fhir_location_identifier="https://confirmgate.local/location-id|coimbra",
        lat=40.2,
        lon=-8.4,
    )


@pytest.fixture
def citizen() -> Actor:
    return Actor(ActorType.CITIZEN, "citizen-1")


@pytest.fixture
def system() -> Actor:
    return Actor(ActorType.SYSTEM, "flag-engine")


@pytest.fixture
def engine() -> DeterministicFlagEngine:
    return DeterministicFlagEngine()


@pytest.fixture
def empty_packet(coimbra_site: SiteRef, citizen: Actor) -> ObservationPacket:
    return ObservationPacket.create(
        coimbra_site,
        author_actor_id=citizen.actor_id,
        submitter_display="Demo",
    )


def sensory_fields() -> list[FieldValue]:
    return [
        FieldValue(code="foam", value="present"),
        FieldValue(code="colour", value="clear"),
        FieldValue(code="smell", value="none"),
    ]


def complete_packet(
    site: SiteRef,
    citizen: Actor,
    *,
    effective: bool = True,
) -> ObservationPacket:
    packet = ObservationPacket.create(
        site,
        author_actor_id=citizen.actor_id,
        submitter_display="Demo",
    )
    for fv in sensory_fields():
        packet.set_field(fv, actor=citizen)
    if effective:
        packet.set_effective_at(
            datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc),
            actor=citizen,
        )
    return packet


class FixedMediaProvider:
    def __init__(self, ctx: MediaContext) -> None:
        self._ctx = ctx

    def for_packet(self, packet: ObservationPacket) -> MediaContext:
        return self._ctx


class FixedDuplicateLookup:
    def __init__(self, matches: tuple[DuplicateMatch, ...] = ()) -> None:
        self._matches = matches

    def find_duplicates(self, packet: ObservationPacket) -> tuple[DuplicateMatch, ...]:
        return self._matches


# Type checkers: ensure providers match Protocol
_: MediaContextProvider = FixedMediaProvider(MediaContext(bound=False))
__: DuplicateLookup = FixedDuplicateLookup()
