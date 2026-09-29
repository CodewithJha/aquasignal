"""Flag rule protocol and deterministic QualityFlag factory."""

from __future__ import annotations

import hashlib
from typing import Protocol

from app.domain.enums import Severity
from app.domain.packet import ObservationPacket
from app.domain.value_objects import QualityFlag
from app.flags.schema import FLAG_RULES_VERSION, FieldSchema


class FlagRule(Protocol):
    """Pure, side-effect-free rule: packet → zero or more QualityFlag."""

    rule_id_prefix: str

    def evaluate(
        self, packet: ObservationPacket, *, schema: FieldSchema
    ) -> list[QualityFlag]:
        ...


def deterministic_flag_id(
    *,
    rule_id: str,
    code: str,
    severity: Severity,
    evidence_refs: tuple[str, ...] = (),
) -> str:
    payload = "|".join(
        [
            rule_id,
            code,
            severity.value,
            ",".join(sorted(evidence_refs)),
        ]
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"flg_{digest}"


def build_flag(
    *,
    rule_id: str,
    severity: Severity,
    code: str,
    message: str,
    evidence_refs: tuple[str, ...] | list[str] = (),
    overridable: bool = True,
    rule_version: str = FLAG_RULES_VERSION,
) -> QualityFlag:
    refs = tuple(evidence_refs)
    return QualityFlag(
        flag_id=deterministic_flag_id(
            rule_id=rule_id,
            code=code,
            severity=severity,
            evidence_refs=refs,
        ),
        rule_id=rule_id,
        rule_version=rule_version,
        severity=severity,
        code=code,
        message=message,
        evidence_refs=refs,
        overridable=overridable,
    )
