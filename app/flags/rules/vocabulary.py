"""Vocabulary rules — internal domain enums only (not OAH FHIR codes)."""

from __future__ import annotations

from app.domain.enums import Severity
from app.domain.packet import ObservationPacket
from app.domain.value_objects import QualityFlag
from app.flags.rules.base import build_flag
from app.flags.schema import FieldSchema


class VocabularyRule:
    rule_id_prefix = "vocabulary"

    def evaluate(
        self, packet: ObservationPacket, *, schema: FieldSchema
    ) -> list[QualityFlag]:
        flags: list[QualityFlag] = []
        for code, field in sorted(packet.fields.items()):
            if code not in schema.allowlist:
                # Domain normally refuses these; still flag if present somehow.
                flags.append(
                    build_flag(
                        rule_id="vocabulary.unknown_code",
                        severity=Severity.HARD_REJECT,
                        code="VOCAB_UNKNOWN_CODE",
                        message=(
                            f"Field code {code!r} is not in the citizen-safe "
                            "allowlist (not an official OAH FHIR code)."
                        ),
                        evidence_refs=(f"fields.{code}",),
                        overridable=False,
                    )
                )
                continue
            if not schema.is_allowed_value(code, field.value):
                flags.append(
                    build_flag(
                        rule_id=f"vocabulary.invalid_value.{code}",
                        severity=Severity.HARD_REJECT,
                        code="VOCAB_INVALID_VALUE",
                        message=(
                            f"Value {field.value!r} is not in the internal domain "
                            f"vocabulary for {code} (TemporaryOahSystem bindings [VERIFY])."
                        ),
                        evidence_refs=(f"fields.{code}",),
                    )
                )
        return flags
