"""FHIR Bundle exporter — StructuralGuard → OahFhirMapper → hash → optional validate.

Invariants:
- Refuse unless workflow_state == FINALIZED.
- NEVER set Observation.status = preliminary.
- Do not claim full OAH IG validator green.
- Domain types only as input; FHIR JSON stays in this package.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.domain.models import ObservationPacket, WorkflowState
from app.flags.schema import FLAG_RULES_VERSION
from app.fhir.errors import (
    FhirExportRefused,
    FhirValidationFailure,
    FhirValidatorUnavailable,
    MissingRequiredOahData,
    StructuralGuardFailure,
    UnsupportedOahMapping,
)
from app.fhir.guard import StructuralGuard, check_exportable
from app.fhir.mapper import OahFhirMapper
from app.fhir.serialize import bundle_content_hash, canonical_bundle_json
from app.fhir.validator import FhirValidatorPort, NullFhirValidator
from app.fhir.versions import OAH_FHIR_MAPPER_VERSION


@dataclass(frozen=True, slots=True)
class FhirExportResult:
    """Successful export artifacts for provenance (HITL Q6 / Q7)."""

    bundle: dict[str, Any]
    bundle_hash: str
    mapper_version: str
    rule_engine_version: str
    canonical_json: str


def export_bundle(
    packet: ObservationPacket,
    *,
    validator: FhirValidatorPort | None = None,
    mapper: OahFhirMapper | None = None,
) -> dict[str, Any]:
    """Export a Bundle only for FINALIZED packets.

    Returns the Bundle dict for backward compatibility with Phase 1 callers.
    Prefer :func:`export_bundle_with_meta` when bundle_hash / mapper_version
    must be recorded in provenance.
    """
    return export_bundle_with_meta(
        packet, validator=validator, mapper=mapper
    ).bundle


def export_bundle_with_meta(
    packet: ObservationPacket,
    *,
    validator: FhirValidatorPort | None = None,
    mapper: OahFhirMapper | None = None,
) -> FhirExportResult:
    """Guard → map → canonical hash → optional validate."""
    if packet.workflow_state != WorkflowState.FINALIZED:
        raise FhirExportRefused(
            f"Refuse FHIR export: packet {packet.packet_id} is "
            f"{packet.workflow_state.value}, not FINALIZED. "
            "App workflow state ≠ FHIR status; no Observation exists until finalize."
        )

    check_exportable(packet)

    active_mapper = mapper or OahFhirMapper()
    bundle = active_mapper.map_bundle(packet)

    # Hard safety: never allow preliminary on any Observation in the Bundle.
    for entry in bundle.get("entry") or []:
        resource = entry.get("resource") or {}
        if resource.get("resourceType") == "Observation":
            status = resource.get("status")
            if status == "preliminary":
                raise StructuralGuardFailure(
                    "Observation.status=preliminary is forbidden for OAH export"
                )
            if status != "final":
                raise StructuralGuardFailure(
                    f"Observation.status must be final; got {status!r}"
                )

    canonical = canonical_bundle_json(bundle)
    digest = bundle_content_hash(bundle)

    active_validator = validator if validator is not None else NullFhirValidator()
    try:
        active_validator.validate_bundle(bundle)
    except FhirValidatorUnavailable:
        raise
    except FhirValidationFailure:
        raise

    return FhirExportResult(
        bundle=bundle,
        bundle_hash=digest,
        mapper_version=OAH_FHIR_MAPPER_VERSION,
        rule_engine_version=packet.rule_engine_version or FLAG_RULES_VERSION,
        canonical_json=canonical,
    )


__all__ = [
    "FhirExportRefused",
    "FhirExportResult",
    "FhirValidationFailure",
    "FhirValidatorUnavailable",
    "MissingRequiredOahData",
    "StructuralGuard",
    "StructuralGuardFailure",
    "UnsupportedOahMapping",
    "check_exportable",
    "export_bundle",
    "export_bundle_with_meta",
]
