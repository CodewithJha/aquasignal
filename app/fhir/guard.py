"""StructuralGuard — refuse FHIR export unless FINALIZED packet is export-ready.

Domain must not import this module. Guard reads domain types only.
"""

from __future__ import annotations

from app.domain.enums import WorkflowState
from app.domain.packet import ObservationPacket
from app.flags.schema import FLAG_RULES_VERSION
from app.fhir.errors import (
    MissingRequiredOahData,
    StructuralGuardFailure,
    UnsupportedOahMapping,
)
from app.fhir.registry import (
    ANNOTATION_ONLY_INTERNAL_KEYS,
    SUPPORTED_CODED_INTERNAL_KEYS,
    UNSUPPORTED_CODED_INTERNAL_KEYS,
    value_coding_for,
)
from app.fhir.versions import OAH_FHIR_MAPPER_VERSION


class StructuralGuard:
    """Pre-mapper refusal gate. Prefer refusal over fabricating mandatory elements."""

    def check(self, packet: ObservationPacket) -> None:
        if packet is None:
            raise StructuralGuardFailure("packet is required")

        if packet.workflow_state != WorkflowState.FINALIZED:
            raise StructuralGuardFailure(
                f"Refuse FHIR export: packet {packet.packet_id} is "
                f"{packet.workflow_state.value}, not FINALIZED. "
                "CONFIRMED alone is insufficient (app state ≠ FHIR status)."
            )

        if packet.workflow_state in {
            WorkflowState.WITHDRAWN,
            WorkflowState.REJECTED,
        }:
            raise StructuralGuardFailure(
                f"Refuse FHIR export: packet is {packet.workflow_state.value}"
            )

        site = packet.site
        if site is None:
            raise MissingRequiredOahData("site is required for LocationOah")

        if not site.fhir_location_identifier:
            raise MissingRequiredOahData(
                "SiteRef.fhir_location_identifier is required for LocationOah.identifier"
            )

        confirmation = packet.confirmation
        if confirmation is None:
            raise StructuralGuardFailure(
                "FINALIZED packet lacks confirmation snapshot"
            )

        if not confirmation.matches_fields(packet.fields):
            raise StructuralGuardFailure(
                "confirmation snapshot hash does not match current fields"
            )

        if packet.standing_hard_rejects():
            raise StructuralGuardFailure(
                "standing hard_reject flags block FHIR export"
            )
        if packet.standing_soft_blocks():
            raise StructuralGuardFailure(
                "standing soft_block_finalize flags block FHIR export"
            )

        if packet.effective_at is None:
            raise MissingRequiredOahData(
                "effective_at is required (Observation.effective[x] 1..1)"
            )

        performer = packet.submitter_display or (
            f"{confirmation.confirmed_by.actor_type.value}:"
            f"{confirmation.confirmed_by.actor_id}"
            if confirmation.confirmed_by
            else None
        )
        if not performer or not str(performer).strip():
            raise MissingRequiredOahData(
                "performer display is required (Observation.performer 1..)"
            )

        if not OAH_FHIR_MAPPER_VERSION:
            raise StructuralGuardFailure("OAH_FHIR_MAPPER_VERSION is unknown")
        if not FLAG_RULES_VERSION:
            raise StructuralGuardFailure("FLAG_RULES_VERSION is unknown")

        snapshot_codes = {f.code for f in confirmation.fields}
        for code in sorted(snapshot_codes):
            if code in UNSUPPORTED_CODED_INTERNAL_KEYS:
                raise UnsupportedOahMapping(
                    f"Internal field {code!r} has no verified TemporaryOahSystem "
                    "Observation mapping (typed WithComp slices required)"
                )
            if code in ANNOTATION_ONLY_INTERNAL_KEYS:
                continue
            if code not in SUPPORTED_CODED_INTERNAL_KEYS:
                raise UnsupportedOahMapping(
                    f"Internal field {code!r} is not in the verified export registry"
                )
            # Validate value is mappable now (fail closed before mapper half-builds).
            field = next(f for f in confirmation.fields if f.code == code)
            value_coding_for(code, field.value)

        # Foam/colour/smell triad may be annotation-only for colour/smell, but
        # at least one coded Observation should be producible when foam present.
        coded = snapshot_codes & SUPPORTED_CODED_INTERNAL_KEYS
        if not coded:
            raise MissingRequiredOahData(
                "confirmation snapshot has no verified coded indicators to export"
            )


def check_exportable(packet: ObservationPacket) -> None:
    """Module-level convenience used by the exporter."""
    StructuralGuard().check(packet)
