"""OahFhirMapper — domain snapshot → IG-shaped Bundle dict.

No FastAPI / web imports. Reads domain + registry only. Does not validate IG
package conformance (optional FhirValidatorPort).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from app.domain.packet import ObservationPacket
from app.domain.value_objects import FieldValue
from app.fhir.errors import MissingRequiredOahData
from app.fhir.registry import (
    ANNOTATION_ONLY_INTERNAL_KEYS,
    observation_code_for,
    value_coding_for,
)
from app.fhir.versions import (
    LOCATION_IDENTIFIER_SYSTEM,
    OAH_FHIR_MAPPER_VERSION,
    PROFILE_LOCATION_OAH,
    PROFILE_OBSERVATION_INDICATORS_OAH,
)


def _location_id(packet_id: str) -> str:
    return f"loc-{packet_id}"


def _observation_id(packet_id: str, internal_key: str) -> str:
    return f"obs-{internal_key.replace('_', '-')}-{packet_id}"


# Fixed namespace so entry fullUrls are stable per packet (bundle_hash reproducible).
_FULL_URL_NAMESPACE = uuid.UUID("5b0f2a8e-3c1d-5e7a-9f4b-6d2c8a1e0b73")


def _full_url(resource_id: str) -> str:
    return f"urn:uuid:{uuid.uuid5(_FULL_URL_NAMESPACE, resource_id)}"


def _parse_location_identifier(raw: str) -> tuple[str, str]:
    """Return (system, value). Prefer verified OAH example system for value."""
    text = raw.strip()
    if "|" in text:
        system, _, value = text.partition("|")
        value = value.strip()
        # Always emit verified IG example system; keep value portion.
        return LOCATION_IDENTIFIER_SYSTEM, value or text
    return LOCATION_IDENTIFIER_SYSTEM, text


def _effective_datetime(when: datetime) -> str:
    if when.tzinfo is None:
        return when.isoformat() + "Z"
    return when.isoformat()


def _performer_display(packet: ObservationPacket) -> str:
    if packet.submitter_display and packet.submitter_display.strip():
        return packet.submitter_display.strip()
    conf = packet.confirmation
    if conf is not None:
        return f"{conf.confirmed_by.actor_type.value}:{conf.confirmed_by.actor_id}"
    raise MissingRequiredOahData("performer display unavailable")


def _build_location(packet: ObservationPacket) -> dict[str, Any]:
    site = packet.site
    system, value = _parse_location_identifier(site.fhir_location_identifier or site.site_id)
    resource: dict[str, Any] = {
        "resourceType": "Location",
        "id": _location_id(packet.packet_id),
        "meta": {"profile": [PROFILE_LOCATION_OAH]},
        "identifier": [{"system": system, "value": value}],
        "name": site.display_name,
        "mode": "instance",
    }
    if site.lat is not None and site.lon is not None:
        resource["position"] = {
            "latitude": site.lat,
            "longitude": site.lon,
        }
    return resource


def _annotation_note(
    fields_by_code: dict[str, FieldValue],
) -> list[dict[str, str]] | None:
    parts: list[str] = []
    for key in sorted(ANNOTATION_ONLY_INTERNAL_KEYS):
        field = fields_by_code.get(key)
        if field is not None:
            parts.append(f"{key}={field.value}")
    if not parts:
        return None
    return [
        {
            "text": (
                "ConfirmGate protocol-lite annotation (not TemporaryOahSystem codes): "
                + "; ".join(parts)
            )
        }
    ]


def _build_observation(
    packet: ObservationPacket,
    *,
    internal_key: str,
    field: FieldValue,
    fields_by_code: dict[str, FieldValue],
) -> dict[str, Any]:
    code = observation_code_for(internal_key)
    value = value_coding_for(internal_key, field.value)
    assert packet.effective_at is not None
    resource: dict[str, Any] = {
        "resourceType": "Observation",
        "id": _observation_id(packet.packet_id, internal_key),
        "meta": {"profile": [PROFILE_OBSERVATION_INDICATORS_OAH]},
        "status": "final",
        "code": code.as_codeable_concept(),
        "subject": {"reference": _full_url(_location_id(packet.packet_id))},
        "effectiveDateTime": _effective_datetime(packet.effective_at),
        "performer": [{"display": _performer_display(packet)}],
        "valueCodeableConcept": value.as_codeable_concept(),
    }
    if internal_key == "foam":
        note = _annotation_note(fields_by_code)
        if note:
            resource["note"] = note
    return resource


class OahFhirMapper:
    """Map FINALIZED confirmed snapshot → Bundle (collection)."""

    version: str = OAH_FHIR_MAPPER_VERSION

    def map_bundle(self, packet: ObservationPacket) -> dict[str, Any]:
        confirmation = packet.confirmation
        if confirmation is None:
            raise MissingRequiredOahData("confirmation snapshot required")

        fields_by_code = {f.code: f for f in confirmation.fields}
        location = _build_location(packet)

        observations: list[dict[str, Any]] = []
        for internal_key in sorted(
            k
            for k in fields_by_code
            if k not in ANNOTATION_ONLY_INTERNAL_KEYS
            and k
            in {
                "foam",
                "macrophytes",
                "riparian_vegetation",
                "hydromorphology",
            }
        ):
            observations.append(
                _build_observation(
                    packet,
                    internal_key=internal_key,
                    field=fields_by_code[internal_key],
                    fields_by_code=fields_by_code,
                )
            )

        if not observations:
            raise MissingRequiredOahData(
                "no verified Observations produced from confirmation snapshot"
            )

        # Deterministic entry order: Location then Observations by code.
        observations.sort(
            key=lambda obs: obs["code"]["coding"][0]["code"]
        )

        bundle_id = packet.fhir_bundle_id or packet.packet_id
        entries: list[dict[str, Any]] = [
            {"fullUrl": _full_url(location["id"]), "resource": location}
        ]
        for obs in observations:
            entries.append(
                {"fullUrl": _full_url(obs["id"]), "resource": obs}
            )

        return {
            "resourceType": "Bundle",
            "id": bundle_id,
            "type": "collection",
            "meta": {
                "tag": [
                    {
                        "system": "https://confirmgate.local/fhir/mapper",
                        "code": OAH_FHIR_MAPPER_VERSION,
                        "display": (
                            "ConfirmGate OahFhirMapper — IG-shaped structural "
                            "export; not claimed as hl7.eu.fhir.oah validator green"
                        ),
                    }
                ]
            },
            "entry": entries,
        }
