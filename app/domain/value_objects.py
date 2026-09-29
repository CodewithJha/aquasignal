"""Domain value objects — immutable where practical."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.domain.cities import OAH_CITIES
from app.domain.enums import ActorType, FieldSource, Severity
from app.domain.errors import DomainValidationError, InvalidFieldValue


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class Actor:
    """Who performs a domain action. AI cannot confirm or finalize."""

    actor_type: ActorType
    actor_id: str = "anonymous"

    @property
    def is_human(self) -> bool:
        return self.actor_type in {ActorType.CITIZEN, ActorType.REVIEWER}

    @property
    def is_ai(self) -> bool:
        return self.actor_type == ActorType.AI_PROVIDER


@dataclass(frozen=True, slots=True)
class SiteRef:
    """Seeded OAH city / demo reach. Immutable for the hackathon."""

    site_id: str
    city: str
    display_name: str
    lat: float | None = None
    lon: float | None = None
    fhir_location_identifier: str | None = None

    def __post_init__(self) -> None:
        if self.city not in OAH_CITIES:
            raise DomainValidationError(
                f"city must be one of {sorted(OAH_CITIES)}; got {self.city!r}"
            )


# Abstract citizen-safe field keys for Phase 2. Exact TemporaryOahSystem /
# value-set bindings remain [VERIFY] — do not invent fake OAH system URIs here.
CITIZEN_SAFE_FIELD_CODES: frozenset[str] = frozenset(
    {
        "macrophytes",
        "macrophytes_non_native",
        "riparian_vegetation",
        "riparian_non_native",
        "hydromorphology",
        "foam",
        "colour",
        "smell",
    }
)

# Explicit exclude list — storage refused at domain boundary (FR-002).
EXCLUDED_FIELD_CODES: frozenset[str] = frozenset(
    {
        "bmwp",
        "diatoms",
        "pathogen",
        "pathogens",
        "arg",
        "amr",
        "pharmaceuticals",
        "disease_prevalence",
        "well_being",
        "diptera_trap_count",
        "fish",
        "amphibians",
        "fecal_coliforms",
    }
)


@dataclass(frozen=True, slots=True)
class FieldValue:
    """One protocol-lite datum. Codes are abstract until IG binding is verified."""

    code: str
    value: str | int | float | bool
    unit: str | None = None
    source: FieldSource = FieldSource.HUMAN
    confidence: float | None = None

    def __post_init__(self) -> None:
        code = self.code.strip()
        if not code:
            raise InvalidFieldValue("field code must be non-empty")
        lowered = code.lower().replace("#", "").replace("-", "_")
        if lowered in EXCLUDED_FIELD_CODES or code.lower() in EXCLUDED_FIELD_CODES:
            raise InvalidFieldValue(
                f"field code {code!r} is excluded from citizen protocol-lite storage"
            )
        if code not in CITIZEN_SAFE_FIELD_CODES and lowered not in CITIZEN_SAFE_FIELD_CODES:
            raise InvalidFieldValue(
                f"field code {code!r} is not in the citizen-safe allowlist "
                f"(bindings TemporaryOahSystem still [VERIFY])"
            )
        if self.confidence is not None and not (0.0 <= self.confidence <= 1.0):
            raise InvalidFieldValue("confidence must be in [0, 1] when provided")


@dataclass(frozen=True, slots=True)
class QualityFlag:
    """Structured fitness signal — not a score."""

    rule_id: str
    severity: Severity
    code: str
    message: str
    flag_id: str = field(default_factory=lambda: f"flg_{uuid4().hex[:12]}")
    rule_version: str = "0.0.0"
    evidence_refs: tuple[str, ...] = ()
    overridable: bool = True
    override_reason: str | None = None
    overridden_by: str | None = None

    @property
    def is_overridden(self) -> bool:
        return self.override_reason is not None

    @property
    def is_standing_hard_reject(self) -> bool:
        return (
            self.severity == Severity.HARD_REJECT and not self.is_overridden
        )

    @property
    def is_standing_soft_block(self) -> bool:
        return (
            self.severity == Severity.SOFT_BLOCK_FINALIZE and not self.is_overridden
        )

    def with_override(self, *, reason: str, actor: Actor) -> QualityFlag:
        if not reason.strip():
            raise DomainValidationError("override_reason is required")
        if not self.overridable:
            raise DomainValidationError(f"flag {self.flag_id} is not overridable")
        if not actor.is_human:
            raise DomainValidationError("only a human actor may override a flag")
        return replace(
            self,
            override_reason=reason.strip(),
            overridden_by=f"{actor.actor_type.value}:{actor.actor_id}",
        )


@dataclass(frozen=True, slots=True)
class ConfirmationSnapshot:
    """Frozen field attestation + deterministic content hash."""

    fields: tuple[FieldValue, ...]
    confirmed_at: datetime
    confirmed_by: Actor
    content_hash: str

    @staticmethod
    def from_fields(
        fields: dict[str, FieldValue],
        *,
        actor: Actor,
        confirmed_at: datetime | None = None,
    ) -> ConfirmationSnapshot:
        ordered = tuple(sorted(fields.values(), key=lambda f: f.code))
        payload = [
            {
                "code": f.code,
                "value": f.value,
                "unit": f.unit,
                "source": f.source.value,
            }
            for f in ordered
        ]
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return ConfirmationSnapshot(
            fields=ordered,
            confirmed_at=confirmed_at or _utc_now(),
            confirmed_by=actor,
            content_hash=digest,
        )

    def matches_fields(self, fields: dict[str, FieldValue]) -> bool:
        return self.content_hash == ConfirmationSnapshot.from_fields(
            fields, actor=self.confirmed_by, confirmed_at=self.confirmed_at
        ).content_hash


def field_map_hash(fields: dict[str, FieldValue]) -> str:
    """Deterministic hash of current field map (for provenance diffs)."""
    return ConfirmationSnapshot.from_fields(
        fields,
        actor=Actor(ActorType.SYSTEM, "hash"),
    ).content_hash


def serialize_field(f: FieldValue) -> dict[str, Any]:
    return {
        "code": f.code,
        "value": f.value,
        "unit": f.unit,
        "source": f.source.value,
        "confidence": f.confidence,
    }


def serialize_flag(flag: QualityFlag) -> dict[str, Any]:
    return {
        "flag_id": flag.flag_id,
        "rule_id": flag.rule_id,
        "rule_version": flag.rule_version,
        "severity": flag.severity.value,
        "code": flag.code,
        "message": flag.message,
        "evidence_refs": list(flag.evidence_refs),
        "overridable": flag.overridable,
        "override_reason": flag.override_reason,
        "overridden_by": flag.overridden_by,
    }
