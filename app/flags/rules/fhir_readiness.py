"""FHIR-readiness prerequisites from domain state — does NOT create FHIR."""

from __future__ import annotations

from app.domain.enums import Severity, WorkflowState
from app.domain.packet import ObservationPacket
from app.domain.value_objects import QualityFlag
from app.flags.rules.base import build_flag
from app.flags.schema import FieldSchema


class FhirReadinessRule:
    """Evaluate export preconditions knowable from the domain packet.

    Never imports FHIR libraries or emits Observations.
    """

    rule_id_prefix = "fhir_readiness"

    def evaluate(
        self, packet: ObservationPacket, *, schema: FieldSchema
    ) -> list[QualityFlag]:
        _ = schema
        flags: list[QualityFlag] = []

        if packet.effective_at is None:
            flags.append(
                build_flag(
                    rule_id="fhir_readiness.missing_effective_at",
                    severity=Severity.SOFT_BLOCK_FINALIZE,
                    code="FHIR_MISSING_EFFECTIVE",
                    message=(
                        "effective_at is required before FHIR export finalization."
                    ),
                    evidence_refs=("effective_at",),
                )
            )

        if not packet.site.fhir_location_identifier:
            flags.append(
                build_flag(
                    rule_id="fhir_readiness.missing_location_identifier",
                    severity=Severity.SOFT_BLOCK_FINALIZE,
                    code="FHIR_MISSING_LOCATION_ID",
                    message=(
                        "Site FHIR location identifier is missing "
                        "(LocationOah identifier binding still [VERIFY])."
                    ),
                    evidence_refs=("site.fhir_location_identifier",),
                )
            )

        if (
            packet.workflow_state
            in {WorkflowState.CONFIRMED, WorkflowState.FINALIZED}
            and packet.confirmation is None
        ):
            flags.append(
                build_flag(
                    rule_id="fhir_readiness.missing_confirmation_snapshot",
                    severity=Severity.SOFT_BLOCK_FINALIZE,
                    code="FHIR_MISSING_CONFIRMATION",
                    message=(
                        "Confirmed/finalized packet lacks a confirmation snapshot."
                    ),
                    evidence_refs=("confirmation",),
                    overridable=False,
                )
            )

        return flags
