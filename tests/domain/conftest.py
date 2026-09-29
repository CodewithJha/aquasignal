"""Shared fixtures for domain contract tests."""

from __future__ import annotations

import pytest

from app.domain.enums import ActorType, Severity
from app.domain.packet import ObservationPacket, make_flag
from app.domain.value_objects import Actor, FieldValue, SiteRef


@pytest.fixture
def coimbra_site() -> SiteRef:
    return SiteRef(
        site_id="coimbra",
        city="Coimbra",
        display_name="Coimbra, Portugal",
        fhir_location_identifier="https://confirmgate.local/location-id|coimbra",
    )


@pytest.fixture
def citizen() -> Actor:
    return Actor(ActorType.CITIZEN, "citizen-1")


@pytest.fixture
def reviewer() -> Actor:
    return Actor(ActorType.REVIEWER, "reviewer-1")


@pytest.fixture
def system() -> Actor:
    return Actor(ActorType.SYSTEM, "flag-engine")


@pytest.fixture
def ai_actor() -> Actor:
    return Actor(ActorType.AI_PROVIDER, "null")


@pytest.fixture
def packet(coimbra_site: SiteRef, citizen: Actor) -> ObservationPacket:
    return ObservationPacket.create(
        coimbra_site,
        author_actor_id=citizen.actor_id,
        submitter_display="Demo Citizen",
    )


def foam_field(*, source=None) -> FieldValue:
    kwargs = {}
    if source is not None:
        kwargs["source"] = source
    return FieldValue(code="foam", value="present", **kwargs)


def hard_flag(**kwargs):
    return make_flag(
        rule_id=kwargs.get("rule_id", "nonclaim.pathogen"),
        severity=Severity.HARD_REJECT,
        code=kwargs.get("code", "NONCLAIM"),
        message=kwargs.get("message", "excluded indicator"),
        overridable=kwargs.get("overridable", True),
    )


def warn_flag():
    return make_flag(
        rule_id="media.blur",
        severity=Severity.WARN,
        code="MEDIA_WARN",
        message="image may be blurry",
    )


def soft_flag():
    return make_flag(
        rule_id="fhir_readiness.missing_effective",
        severity=Severity.SOFT_BLOCK_FINALIZE,
        code="FHIR_SOFT",
        message="effective_at missing",
    )


def reach_awaiting_confirm(
    packet: ObservationPacket,
    *,
    system: Actor,
    citizen: Actor,
    flags=None,
) -> ObservationPacket:
    packet.set_field(foam_field(), actor=citizen)
    packet.apply_flags(flags if flags is not None else [], actor=system)
    packet.mark_awaiting_confirm(actor=system)
    return packet


def reach_confirmed(
    packet: ObservationPacket,
    *,
    system: Actor,
    citizen: Actor,
    flags=None,
) -> ObservationPacket:
    reach_awaiting_confirm(packet, system=system, citizen=citizen, flags=flags)
    packet.confirm(actor=citizen)
    return packet
