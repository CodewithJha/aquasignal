"""Non-claim rules — block prohibited lab/health indicators in structured data.

Deterministic only: inspects suggestion keys and notes for excluded codes.
Does not run NLP or AI. Domain FieldValue construction already refuses
excluded codes into authoritative fields.
"""

from __future__ import annotations

import re

from app.domain.enums import Severity
from app.domain.packet import ObservationPacket
from app.domain.value_objects import QualityFlag
from app.flags.rules.base import build_flag
from app.flags.schema import FieldSchema

# Extra aliases that may appear as suggestion keys / note tokens.
_EXTRA_PROHIBITED = frozenset(
    {
        "bmwp",
        "ibd",
        "efi",
        "pathogen",
        "pathogens",
        "disease",
        "outbreak",
        "arg",
        "amr",
        "pharmaceutical",
        "pharmaceuticals",
        "diatoms",
        "diagnosis",
    }
)


def _normalize_key(raw: str) -> str:
    return raw.strip().lower().replace("#", "").replace("-", "_").replace(" ", "_")


class NonClaimRule:
    rule_id_prefix = "nonclaim"

    def evaluate(
        self, packet: ObservationPacket, *, schema: FieldSchema
    ) -> list[QualityFlag]:
        flags: list[QualityFlag] = []
        prohibited = set(schema.excluded) | _EXTRA_PROHIBITED

        for key in sorted(packet.suggestions.keys()):
            norm = _normalize_key(str(key))
            if norm in prohibited:
                flags.append(
                    build_flag(
                        rule_id=f"nonclaim.suggestion.{norm}",
                        severity=Severity.HARD_REJECT,
                        code="NONCLAIM_PROHIBITED",
                        message=(
                            f"Suggestion key {key!r} claims a prohibited "
                            "lab/health indicator outside protocol-lite scope."
                        ),
                        evidence_refs=(f"suggestions.{key}",),
                        overridable=False,
                    )
                )

        # Authoritative fields: domain should already refuse excluded codes.
        # Defense in depth if a bypass somehow stores them.
        for code in sorted(packet.fields.keys()):
            norm = _normalize_key(code)
            if norm in prohibited:
                flags.append(
                    build_flag(
                        rule_id=f"nonclaim.field.{norm}",
                        severity=Severity.HARD_REJECT,
                        code="NONCLAIM_PROHIBITED",
                        message=(
                            f"Field {code!r} is excluded from citizen protocol-lite "
                            "(pathogen/BMWP/disease/lab indicators are not supported)."
                        ),
                        evidence_refs=(f"fields.{code}",),
                        overridable=False,
                    )
                )

        notes = packet.notes
        if notes:
            tokens = set(re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", notes.lower()))
            hits = sorted(tokens & prohibited)
            for hit in hits:
                flags.append(
                    build_flag(
                        rule_id=f"nonclaim.notes.{hit}",
                        severity=Severity.HARD_REJECT,
                        code="NONCLAIM_PROHIBITED",
                        message=(
                            f"Notes mention prohibited indicator token {hit!r}. "
                            "ConfirmGate does not accept lab/pathogen/disease claims "
                            "in free-text notes."
                        ),
                        evidence_refs=("notes",),
                        overridable=False,
                    )
                )
        return flags
