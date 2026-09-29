"""Phase 5 FHIR StructuralGuard / mapper / exporter tests."""

from __future__ import annotations

import ast
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.domain.enums import ActorType, WorkflowState
from app.domain.packet import ObservationPacket
from app.domain.value_objects import Actor, FieldValue, SiteRef
from app.fhir.errors import (
    FhirExportRefused,
    FhirValidationFailure,
    FhirValidatorUnavailable,
    MissingRequiredOahData,
    StructuralGuardFailure,
    UnsupportedOahMapping,
)
from app.fhir.exporter import export_bundle, export_bundle_with_meta
from app.fhir.guard import StructuralGuard
from app.fhir.mapper import OahFhirMapper
from app.fhir.serialize import bundle_content_hash, canonical_bundle_json
from app.fhir.validator import (
    NullFhirValidator,
    RejectingFhirValidator,
    UnavailableFhirValidator,
)
from app.fhir.versions import (
    LOCATION_IDENTIFIER_SYSTEM,
    OAH_FHIR_MAPPER_VERSION,
    PROFILE_LOCATION_OAH,
    PROFILE_OBSERVATION_INDICATORS_OAH,
    TEMPORARY_OAH_SYSTEM,
)
from app.flags.schema import FLAG_RULES_VERSION


def _site(**kwargs) -> SiteRef:
    base = dict(
        site_id="coimbra",
        city="Coimbra",
        display_name="Coimbra, Portugal",
        fhir_location_identifier="coimbra",
        lat=40.2033,
        lon=-8.4103,
    )
    base.update(kwargs)
    return SiteRef(**base)


def _packet_to(
    state: WorkflowState,
    *,
    with_effective: bool = True,
    with_location_id: bool = True,
    fields: list[FieldValue] | None = None,
) -> ObservationPacket:
    site = _site(
        fhir_location_identifier="coimbra" if with_location_id else None,
        lat=40.2033 if with_location_id else None,
        lon=-8.4103 if with_location_id else None,
    )
    # SiteRef requires fhir_location_identifier as optional; for missing id use empty site
    if not with_location_id:
        site = SiteRef(
            site_id="coimbra",
            city="Coimbra",
            display_name="Coimbra, Portugal",
            fhir_location_identifier=None,
        )
    citizen = Actor(ActorType.CITIZEN, "t")
    system = Actor(ActorType.SYSTEM, "t")
    packet = ObservationPacket.create(
        site,
        author_actor_id=citizen.actor_id,
        submitter_display="Demo Citizen",
        effective_at=(
            datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)
            if with_effective
            else None
        ),
        packet_id="pktfixed001abc",
    )
    default_fields = fields or [
        FieldValue(code="foam", value="present"),
        FieldValue(code="colour", value="clear"),
        FieldValue(code="smell", value="none"),
    ]
    for f in default_fields:
        packet.set_field(f, actor=citizen)

    if state == WorkflowState.RECEIVED:
        return packet

    packet.apply_flags([], actor=system)
    if state == WorkflowState.FLAGGED:
        return packet
    if state == WorkflowState.REJECTED:
        packet.reject(actor=system, reason_code="other", explanation="test")
        return packet
    if state == WorkflowState.WITHDRAWN:
        packet.withdraw(actor=citizen)
        return packet
    if state == WorkflowState.NEEDS_REVIEW:
        packet.request_review(actor=system)
        return packet

    packet.mark_awaiting_confirm(actor=system)
    if state == WorkflowState.AWAITING_CONFIRM:
        return packet

    packet.confirm(actor=citizen)
    if state == WorkflowState.CONFIRMED:
        return packet

    if state == WorkflowState.FINALIZED:
        packet.finalize(actor=system)
        return packet

    raise AssertionError(f"unsupported state {state}")


# --- Guard -----------------------------------------------------------------


@pytest.mark.parametrize(
    "state",
    [
        WorkflowState.RECEIVED,
        WorkflowState.FLAGGED,
        WorkflowState.AWAITING_CONFIRM,
        WorkflowState.NEEDS_REVIEW,
        WorkflowState.CONFIRMED,
        WorkflowState.REJECTED,
        WorkflowState.WITHDRAWN,
    ],
)
def test_structural_guard_refuses_non_finalized(state: WorkflowState) -> None:
    packet = _packet_to(state)
    with pytest.raises((StructuralGuardFailure, FhirExportRefused)):
        StructuralGuard().check(packet)
    with pytest.raises(FhirExportRefused):
        export_bundle(packet)


def test_structural_guard_accepts_finalized() -> None:
    packet = _packet_to(WorkflowState.FINALIZED)
    StructuralGuard().check(packet)
    result = export_bundle_with_meta(packet)
    assert result.bundle["resourceType"] == "Bundle"


def test_confirmed_cannot_export_regression() -> None:
    packet = _packet_to(WorkflowState.CONFIRMED)
    with pytest.raises(FhirExportRefused):
        export_bundle(packet)


def test_guard_requires_effective_at() -> None:
    packet = _packet_to(WorkflowState.FINALIZED, with_effective=False)
    with pytest.raises(MissingRequiredOahData):
        StructuralGuard().check(packet)


def test_guard_requires_location_identifier() -> None:
    packet = _packet_to(WorkflowState.FINALIZED, with_location_id=False)
    with pytest.raises(MissingRequiredOahData):
        StructuralGuard().check(packet)


def test_guard_refuses_unsupported_non_native() -> None:
    packet = _packet_to(
        WorkflowState.FINALIZED,
        fields=[
            FieldValue(code="foam", value="present"),
            FieldValue(code="colour", value="clear"),
            FieldValue(code="smell", value="none"),
            FieldValue(code="macrophytes_non_native", value="true"),
        ],
    )
    with pytest.raises(UnsupportedOahMapping):
        StructuralGuard().check(packet)


def test_guard_refuses_unmapped_riparian_domain_bin() -> None:
    packet = _packet_to(
        WorkflowState.FINALIZED,
        fields=[
            FieldValue(code="foam", value="present"),
            FieldValue(code="colour", value="clear"),
            FieldValue(code="smell", value="none"),
            FieldValue(code="riparian_vegetation", value="0-25"),
        ],
    )
    with pytest.raises(UnsupportedOahMapping):
        StructuralGuard().check(packet)


# --- Mapping ---------------------------------------------------------------


def test_location_profile_and_no_invented_gps_when_missing() -> None:
    packet = _packet_to(WorkflowState.FINALIZED)
    # Clear GPS by rehydrating site without coords but with identifier.
    packet = ObservationPacket.rehydrate(
        packet_id=packet.packet_id,
        site=_site(lat=None, lon=None),
        workflow_state=WorkflowState.FINALIZED,
        author_actor_id="t",
        submitter_display="Demo Citizen",
        effective_at=packet.effective_at,
        fields=dict(packet.fields),
        confirmation=packet.confirmation,
        fhir_bundle_id=packet.fhir_bundle_id,
    )
    bundle = export_bundle(packet)
    loc = next(
        e["resource"]
        for e in bundle["entry"]
        if e["resource"]["resourceType"] == "Location"
    )
    assert PROFILE_LOCATION_OAH in loc["meta"]["profile"]
    assert loc["mode"] == "instance"
    assert loc["identifier"][0]["system"] == LOCATION_IDENTIFIER_SYSTEM
    assert loc["identifier"][0]["value"] == "coimbra"
    assert "position" not in loc


def test_observation_status_final_and_profiles() -> None:
    packet = _packet_to(
        WorkflowState.FINALIZED,
        fields=[
            FieldValue(code="foam", value="present"),
            FieldValue(code="colour", value="brown"),
            FieldValue(code="smell", value="mild"),
            FieldValue(code="macrophytes", value="p"),
            FieldValue(code="hydromorphology", value="a"),
            FieldValue(code="riparian_vegetation", value="21-40-percent"),
        ],
    )
    bundle = export_bundle(packet)
    observations = [
        e["resource"]
        for e in bundle["entry"]
        if e["resource"]["resourceType"] == "Observation"
    ]
    assert observations
    codes = set()
    for obs in observations:
        assert obs["status"] == "final"
        assert obs["status"] != "preliminary"
        assert PROFILE_OBSERVATION_INDICATORS_OAH in obs["meta"]["profile"]
        coding = obs["code"]["coding"][0]
        assert coding["system"] == TEMPORARY_OAH_SYSTEM
        codes.add(coding["code"])
        assert obs["subject"]["reference"] == bundle["entry"][0]["fullUrl"]
        assert "effectiveDateTime" in obs
        assert obs["performer"][0]["display"]
        val = obs["valueCodeableConcept"]["coding"][0]
        assert val["system"] == TEMPORARY_OAH_SYSTEM
    assert "foam" in codes
    assert "macrophytes" in codes
    assert "riparianVegetation" in codes
    assert "morophology" in codes
    foam_obs = next(o for o in observations if o["code"]["coding"][0]["code"] == "foam")
    assert "note" in foam_obs
    assert "colour=" in foam_obs["note"][0]["text"]


# Codes confirmed present in TemporaryOahSystem at hl7-eu/oah commit b907cf0
# (the IG snapshot used for HL7 validator runs; see docs/FHIR-SPEC.md §9).
_OAH_CODES_VALIDATED = frozenset(
    {
        "foam",
        "macrophytes",
        "riparianVegetation",
        "morophology",
        "absent",
        "present",
        "extensive",
        "0-20-percent",
        "21-40-percent",
        "41-60-percent",
        "61-80-percent",
        "81-100-percent",
    }
)

# FHIR R4 dateTime with time component; R4 requires a timezone when time is present.
_R4_DATETIME_WITH_TZ = re.compile(
    r"\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])"
    r"T([01]\d|2[0-3]):[0-5]\d:([0-5]\d|60)(\.\d+)?"
    r"(Z|[+-]((0\d|1[0-3]):[0-5]\d|14:00))"
)


def test_bundle_meets_oah_profile_minimums() -> None:
    packet = _packet_to(
        WorkflowState.FINALIZED,
        fields=[
            FieldValue(code="foam", value="abundant"),
            FieldValue(code="colour", value="grey"),
            FieldValue(code="smell", value="sewage"),
            FieldValue(code="macrophytes", value="e"),
            FieldValue(code="hydromorphology", value="p"),
            FieldValue(code="riparian_vegetation", value="81-100-percent"),
        ],
    )
    bundle = export_bundle(packet)
    loc = bundle["entry"][0]["resource"]
    assert loc["resourceType"] == "Location"
    assert loc["name"]
    assert loc["identifier"] and all(i["system"] and i["value"] for i in loc["identifier"])
    observations = [e["resource"] for e in bundle["entry"][1:]]
    assert len(observations) == 4
    for obs in observations:
        assert obs["resourceType"] == "Observation"
        for element in ("status", "code", "subject", "effectiveDateTime", "performer"):
            assert obs.get(element), element
        assert _R4_DATETIME_WITH_TZ.fullmatch(obs["effectiveDateTime"])
        for concept in (obs["code"], obs["valueCodeableConcept"]):
            for coding in concept["coding"]:
                assert coding["system"] == TEMPORARY_OAH_SYSTEM
                assert coding["code"] in _OAH_CODES_VALIDATED


def test_bundle_type_collection_no_fhir_provenance() -> None:
    packet = _packet_to(WorkflowState.FINALIZED)
    bundle = export_bundle(packet)
    assert bundle["type"] == "collection"
    types = {e["resource"]["resourceType"] for e in bundle["entry"]}
    assert "Provenance" not in types
    assert "Specimen" not in types
    assert "Patient" not in types


def test_unsupported_fake_code_refused_at_domain() -> None:
    with pytest.raises(Exception):
        FieldValue(code="bmwp", value="1")


def test_fake_observation_code_not_in_registry() -> None:
    from app.fhir.registry import observation_code_for

    with pytest.raises(UnsupportedOahMapping):
        observation_code_for("pathogen")


# --- Determinism / provenance ---------------------------------------------


def test_deterministic_hash_and_mapper_version() -> None:
    packet = _packet_to(WorkflowState.FINALIZED)
    r1 = export_bundle_with_meta(packet)
    r2 = export_bundle_with_meta(packet)
    assert r1.bundle_hash == r2.bundle_hash
    assert r1.canonical_json == r2.canonical_json
    assert r1.mapper_version == OAH_FHIR_MAPPER_VERSION
    assert r1.bundle_hash == bundle_content_hash(r1.bundle)
    assert canonical_bundle_json(r1.bundle) == r1.canonical_json

    packet.record_fhir_export_digest(
        actor=Actor(ActorType.SYSTEM, "t"),
        bundle_hash=r1.bundle_hash,
        mapper_version=r1.mapper_version,
    )
    intents = packet.drain_provenance_intents()
    digest = next(i for i in intents if i.action == "fhir.export_digest")
    assert digest.after["bundle_hash"] == r1.bundle_hash
    assert digest.after["mapper_version"] == OAH_FHIR_MAPPER_VERSION


def test_validator_optional_null_and_failures() -> None:
    packet = _packet_to(WorkflowState.FINALIZED)
    ok = export_bundle_with_meta(packet, validator=NullFhirValidator())
    assert ok.bundle_hash

    with pytest.raises(FhirValidationFailure):
        export_bundle_with_meta(packet, validator=RejectingFhirValidator())

    with pytest.raises(FhirValidatorUnavailable):
        export_bundle_with_meta(packet, validator=UnavailableFhirValidator())


# --- Architecture ----------------------------------------------------------


def test_domain_and_flags_do_not_import_fhir() -> None:
    root = Path(__file__).resolve().parents[1] / "app"
    for pkg in ("domain", "flags"):
        for py in (root / pkg).rglob("*.py"):
            tree = ast.parse(py.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    parts = node.module.split(".")
                    if parts[0] == "app" and len(parts) > 1:
                        assert parts[1] != "fhir", f"{py} imports app.fhir"


def test_mapper_does_not_import_web() -> None:
    fhir_root = Path(__file__).resolve().parents[1] / "app" / "fhir"
    for py in fhir_root.rglob("*.py"):
        tree = ast.parse(py.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                parts = node.module.split(".")
                if parts[0] == "app" and len(parts) > 1:
                    assert parts[1] != "web", f"{py} imports app.web"
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[0] not in {
                        "fastapi",
                        "starlette",
                    }


def test_mapper_version_constant() -> None:
    assert OAH_FHIR_MAPPER_VERSION == "0.1.1"
    assert FLAG_RULES_VERSION
    assert OahFhirMapper.version == OAH_FHIR_MAPPER_VERSION


def _all_references(node) -> list[str]:
    refs: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "reference" and isinstance(value, str):
                refs.append(value)
            else:
                refs.extend(_all_references(value))
    elif isinstance(node, list):
        for item in node:
            refs.extend(_all_references(item))
    return refs


def test_bundle_full_urls_are_uuids_and_references_resolve() -> None:
    packet = _packet_to(
        WorkflowState.FINALIZED,
        fields=[
            FieldValue(code="foam", value="present"),
            FieldValue(code="macrophytes", value="p"),
            FieldValue(code="hydromorphology", value="a"),
        ],
    )
    bundle = export_bundle(packet)
    full_urls = [e["fullUrl"] for e in bundle["entry"]]
    assert len(set(full_urls)) == len(full_urls)
    for url in full_urls:
        assert url.startswith("urn:uuid:")
        parsed = uuid.UUID(url.removeprefix("urn:uuid:"))
        assert str(parsed) == url.removeprefix("urn:uuid:")
        assert parsed.variant == uuid.RFC_4122
    refs = _all_references(bundle)
    assert refs, "Observations must reference the Location"
    assert all(not r.startswith("#") for r in refs)
    assert set(refs) <= set(full_urls)
    location_url = next(
        e["fullUrl"] for e in bundle["entry"] if e["resource"]["resourceType"] == "Location"
    )
    for e in bundle["entry"]:
        if e["resource"]["resourceType"] == "Observation":
            assert e["resource"]["subject"]["reference"] == location_url
    assert export_bundle(packet)["entry"] == bundle["entry"]
