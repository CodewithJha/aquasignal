"""Completeness rules — provisional required-for-finalize schema [VERIFY]."""

from __future__ import annotations

from app.domain.enums import Severity
from app.domain.packet import ObservationPacket
from app.domain.value_objects import QualityFlag
from app.flags.rules.base import build_flag
from app.flags.schema import FieldSchema


class CompletenessRule:
    rule_id_prefix = "completeness"

    def evaluate(
        self, packet: ObservationPacket, *, schema: FieldSchema
    ) -> list[QualityFlag]:
        flags: list[QualityFlag] = []
        fields = packet.fields

        if not fields:
            flags.append(
                build_flag(
                    rule_id="completeness.no_protocol_fields",
                    severity=Severity.SOFT_BLOCK_FINALIZE,
                    code="COMPLETENESS_EMPTY",
                    message=(
                        "No protocol-lite fields present. Provide citizen-safe "
                        "Annex I–ish observations before finalization."
                    ),
                    evidence_refs=("fields",),
                )
            )
            return flags

        for code in sorted(schema.required_for_finalize):
            if code not in fields:
                flags.append(
                    build_flag(
                        rule_id=f"completeness.required_field.{code}",
                        severity=Severity.SOFT_BLOCK_FINALIZE,
                        code="COMPLETENESS_REQUIRED",
                        message=(
                            f"{code} must be provided before finalization "
                            "(provisional required set; Annex I cardinality still [VERIFY])."
                        ),
                        evidence_refs=(f"fields.{code}",),
                    )
                )
        return flags
