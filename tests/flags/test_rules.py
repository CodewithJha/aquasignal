"""Per-rule FlagEngine tests."""

from __future__ import annotations


import pytest

from app.domain.cities import OAH_CITIES
from app.domain.enums import ActorType, Severity, WorkflowState
from app.domain.errors import InvalidFieldValue
from app.domain.packet import ObservationPacket
from app.domain.value_objects import Actor, FieldValue, SiteRef
from app.flags.engine import DeterministicFlagEngine
from app.flags.ports import DuplicateMatch, MediaAssetSummary, MediaContext
from app.flags.rules.completeness import CompletenessRule
from app.flags.rules.duplicate import DuplicateRule
from app.flags.rules.exif import ExifRule
from app.flags.rules.fhir_readiness import FhirReadinessRule
from app.flags.rules.geo import GeoRule
from app.flags.rules.media import MediaRule
from app.flags.rules.media_heuristic import MediaHeuristicRule
from app.flags.rules.nonclaim import NonClaimRule
from app.flags.rules.vocabulary import VocabularyRule
from app.flags.schema import DEFAULT_SCHEMA
from tests.flags.conftest import (
    FixedDuplicateLookup,
    FixedMediaProvider,
    complete_packet,
    sensory_fields,
)


def test_completeness_missing_required(
    empty_packet: ObservationPacket, citizen: Actor
) -> None:
    empty_packet.set_field(FieldValue(code="foam", value="present"), actor=citizen)
    flags = CompletenessRule().evaluate(empty_packet, schema=DEFAULT_SCHEMA)
    missing = {f.rule_id for f in flags}
    assert "completeness.required_field.colour" in missing
    assert "completeness.required_field.smell" in missing
    assert all(f.severity == Severity.SOFT_BLOCK_FINALIZE for f in flags)


def test_completeness_complete_required(
    coimbra_site, citizen: Actor
) -> None:
    packet = complete_packet(coimbra_site, citizen)
    flags = CompletenessRule().evaluate(packet, schema=DEFAULT_SCHEMA)
    assert flags == []


def test_vocabulary_valid_and_invalid(empty_packet, citizen) -> None:
    empty_packet.set_field(FieldValue(code="macrophytes", value="P"), actor=citizen)
    ok = VocabularyRule().evaluate(empty_packet, schema=DEFAULT_SCHEMA)
    assert not any(f.rule_id.startswith("vocabulary.invalid") for f in ok)

    empty_packet.set_field(
        FieldValue(code="macrophytes", value="luxuriant"), actor=citizen
    )
    bad = VocabularyRule().evaluate(empty_packet, schema=DEFAULT_SCHEMA)
    assert any(f.code == "VOCAB_INVALID_VALUE" for f in bad)


def test_vocabulary_rejects_invented_value_for_each_code(
    empty_packet, citizen
) -> None:
    empty_packet.set_field(FieldValue(code="colour", value="neon"), actor=citizen)
    flags = VocabularyRule().evaluate(empty_packet, schema=DEFAULT_SCHEMA)
    assert any("colour" in f.rule_id for f in flags)


def test_nonclaim_suggestion_and_notes(empty_packet, citizen) -> None:
    empty_packet.apply_suggestions(
        {"bmwp": 42},
        actor=Actor(ActorType.AI_PROVIDER, "null"),
    )
    flags = NonClaimRule().evaluate(empty_packet, schema=DEFAULT_SCHEMA)
    assert any(f.code == "NONCLAIM_PROHIBITED" for f in flags)
    assert all(f.severity == Severity.HARD_REJECT for f in flags)

    empty_packet.apply_suggestions({}, actor=Actor(ActorType.SYSTEM, "sys"))
    empty_packet.set_notes("suspected pathogen", actor=citizen)
    flags2 = NonClaimRule().evaluate(empty_packet, schema=DEFAULT_SCHEMA)
    assert any("pathogen" in f.rule_id for f in flags2)


def test_nonclaim_no_false_positive_on_protocol_fields(
    coimbra_site, citizen
) -> None:
    packet = complete_packet(coimbra_site, citizen)
    packet.set_field(FieldValue(code="macrophytes", value="E"), actor=citizen)
    flags = NonClaimRule().evaluate(packet, schema=DEFAULT_SCHEMA)
    assert flags == []


def test_excluded_field_refused_at_domain() -> None:
    with pytest.raises(InvalidFieldValue):
        FieldValue(code="pathogen", value="yes")


@pytest.mark.parametrize("city", sorted(OAH_CITIES))
def test_geo_supported_cities(city: str, citizen: Actor) -> None:
    site = SiteRef(
        site_id=city.lower(),
        city=city,
        display_name=city,
        fhir_location_identifier=f"id|{city.lower()}",
    )
    packet = ObservationPacket.create(site, author_actor_id=citizen.actor_id)
    flags = GeoRule().evaluate(packet, schema=DEFAULT_SCHEMA)
    assert not any(f.code == "GEO_UNSUPPORTED_CITY" for f in flags)


def test_geo_partial_coords_warn(citizen: Actor) -> None:
    site = SiteRef(
        site_id="oslo",
        city="Oslo",
        display_name="Oslo",
        lat=59.9,
        lon=None,
        fhir_location_identifier="id|oslo",
    )
    packet = ObservationPacket.create(site, author_actor_id=citizen.actor_id)
    flags = GeoRule().evaluate(packet, schema=DEFAULT_SCHEMA)
    assert any(f.code == "GEO_PARTIAL_COORDS" for f in flags)


def test_media_unbound_is_noop(empty_packet) -> None:
    flags = MediaRule().evaluate(empty_packet, schema=DEFAULT_SCHEMA)
    assert flags == []


def test_media_bound_missing_photo_with_vegetation(empty_packet, citizen) -> None:
    empty_packet.set_field(FieldValue(code="macrophytes", value="P"), actor=citizen)
    provider = FixedMediaProvider(MediaContext(bound=True, assets=()))
    flags = MediaRule(media_provider=provider).evaluate(
        empty_packet, schema=DEFAULT_SCHEMA
    )
    assert any(f.rule_id == "media.missing_bank_photo" for f in flags)
    assert all(
        "pathogen" not in f.message.lower() and "bmwp" not in f.message.lower()
        for f in flags
    )


def test_media_invalid_mime(empty_packet) -> None:
    asset = MediaAssetSummary(
        asset_id="a1",
        content_type="application/pdf",
        byte_size=10_000,
    )
    provider = FixedMediaProvider(MediaContext(bound=True, assets=(asset,)))
    flags = MediaRule(media_provider=provider).evaluate(
        empty_packet, schema=DEFAULT_SCHEMA
    )
    assert any(f.code == "MEDIA_MIME" for f in flags)


def test_media_heuristic_noop_without_signals(empty_packet) -> None:
    assert MediaHeuristicRule().evaluate(empty_packet, schema=DEFAULT_SCHEMA) == []


def test_exif_unavailable_and_mismatch(empty_packet) -> None:
    unbound = ExifRule().evaluate(empty_packet, schema=DEFAULT_SCHEMA)
    assert unbound == []

    mismatch = MediaAssetSummary(
        asset_id="a1",
        content_type="image/jpeg",
        claimed_lat=40.0,
        claimed_lon=-8.0,
        exif_lat=41.0,
        exif_lon=-9.0,
        exif_available=True,
    )
    provider = FixedMediaProvider(MediaContext(bound=True, assets=(mismatch,)))
    flags = ExifRule(media_provider=provider).evaluate(
        empty_packet, schema=DEFAULT_SCHEMA
    )
    assert any(f.code == "EXIF_GPS_MISMATCH" for f in flags)
    assert all(f.severity == Severity.WARN for f in flags)


def test_duplicate_null_and_match(empty_packet) -> None:
    assert DuplicateRule().evaluate(empty_packet, schema=DEFAULT_SCHEMA) == []
    lookup = FixedDuplicateLookup(
        (DuplicateMatch(other_packet_id="abc", reason="same site+time"),)
    )
    flags = DuplicateRule(lookup=lookup).evaluate(empty_packet, schema=DEFAULT_SCHEMA)
    assert any(f.code == "DUPLICATE_CANDIDATE" for f in flags)
    assert all(f.severity == Severity.WARN for f in flags)


def test_fhir_readiness_incomplete_and_ready(coimbra_site, citizen) -> None:
    incomplete = ObservationPacket.create(coimbra_site, author_actor_id=citizen.actor_id)
    flags = FhirReadinessRule().evaluate(incomplete, schema=DEFAULT_SCHEMA)
    assert any(f.code == "FHIR_MISSING_EFFECTIVE" for f in flags)

    ready = complete_packet(coimbra_site, citizen, effective=True)
    flags2 = FhirReadinessRule().evaluate(ready, schema=DEFAULT_SCHEMA)
    assert not any(f.code == "FHIR_MISSING_EFFECTIVE" for f in flags2)
    assert not any(f.code == "FHIR_MISSING_LOCATION_ID" for f in flags2)


def test_fhir_readiness_does_not_create_fhir_resources(
    coimbra_site, citizen, engine: DeterministicFlagEngine
) -> None:
    packet = complete_packet(coimbra_site, citizen)
    flags = engine.evaluate(packet)
    assert packet.fhir_bundle_id is None
    assert packet.workflow_state == WorkflowState.RECEIVED
    assert all("Observation" not in f.message for f in flags)


def test_soft_block_does_not_equal_hard(
    empty_packet, citizen, system, engine: DeterministicFlagEngine
) -> None:
    for fv in sensory_fields():
        empty_packet.set_field(fv, actor=citizen)
    # Missing effective_at → soft only
    flags = engine.evaluate(empty_packet)
    soft = [f for f in flags if f.severity == Severity.SOFT_BLOCK_FINALIZE]
    hard = [f for f in flags if f.severity == Severity.HARD_REJECT]
    assert soft
    assert not hard
    empty_packet.apply_flags(flags, actor=system)
    # soft does not block awaiting confirm
    empty_packet.mark_awaiting_confirm(actor=system)
    assert empty_packet.workflow_state == WorkflowState.AWAITING_CONFIRM
