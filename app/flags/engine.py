"""Deterministic FlagEngine — structured findings only, never a trust score.

Orchestrates pure rules: evaluate(packet) → sorted QualityFlag list.
Does not mutate workflow, confirm, finalize, export FHIR, or call AI.
"""

from __future__ import annotations

from typing import Iterable, Protocol, Sequence

from app.domain.enums import Severity
from app.domain.packet import ObservationPacket
from app.domain.value_objects import QualityFlag
from app.flags.ports import (
    DuplicateLookup,
    MediaContextProvider,
    NullDuplicateLookup,
    NullMediaContextProvider,
)
from app.flags.rules import (
    AiAssistRule,
    CompletenessRule,
    DuplicateRule,
    ExifRule,
    FhirReadinessRule,
    GeoRule,
    MediaHeuristicRule,
    MediaRule,
    NonClaimRule,
    VocabularyRule,
)
from app.flags.rules.base import FlagRule
from app.flags.schema import DEFAULT_SCHEMA, FLAG_RULES_VERSION, FieldSchema

__all__ = [
    "Severity",
    "QualityFlag",
    "FlagEngine",
    "NullFlagEngine",
    "DeterministicFlagEngine",
    "FLAG_RULES_VERSION",
]

_SEVERITY_SORT: dict[Severity, int] = {
    Severity.HARD_REJECT: 0,
    Severity.SOFT_BLOCK_FINALIZE: 1,
    Severity.WARN: 2,
}


class FlagEngine(Protocol):
    """Orchestrator: run rule set → list[QualityFlag]. No trust score."""

    @property
    def version(self) -> str:
        ...

    def evaluate(self, packet: ObservationPacket) -> list[QualityFlag]:
        ...


class NullFlagEngine:
    """No-op engine for tests that need empty evaluation."""

    version: str = "null-0.0.0"

    def evaluate(self, packet: ObservationPacket) -> list[QualityFlag]:
        return []


class DeterministicFlagEngine:
    """Composable, side-effect-free FlagEngine.

    Same packet + same rules version ⇒ same flags (including flag_id).
    """

    def __init__(
        self,
        *,
        rules: Sequence[FlagRule] | None = None,
        schema: FieldSchema | None = None,
        media_provider: MediaContextProvider | None = None,
        duplicate_lookup: DuplicateLookup | None = None,
        version: str = FLAG_RULES_VERSION,
    ) -> None:
        self._schema = schema or DEFAULT_SCHEMA
        self._version = version
        media = media_provider or NullMediaContextProvider()
        duplicates = duplicate_lookup or NullDuplicateLookup()
        self._rules: tuple[FlagRule, ...] = tuple(
            rules
            if rules is not None
            else default_rules(media_provider=media, duplicate_lookup=duplicates)
        )

    @property
    def version(self) -> str:
        return self._version

    @property
    def rules(self) -> tuple[FlagRule, ...]:
        return self._rules

    def evaluate(self, packet: ObservationPacket) -> list[QualityFlag]:
        collected: list[QualityFlag] = []
        for rule in self._rules:
            collected.extend(rule.evaluate(packet, schema=self._schema))
        # Ensure every flag carries this engine's version string.
        normalized = [
            QualityFlag(
                flag_id=f.flag_id,
                rule_id=f.rule_id,
                rule_version=self._version,
                severity=f.severity,
                code=f.code,
                message=f.message,
                evidence_refs=f.evidence_refs,
                overridable=f.overridable,
                override_reason=f.override_reason,
                overridden_by=f.overridden_by,
            )
            for f in collected
        ]
        return sort_flags(normalized)


def default_rules(
    *,
    media_provider: MediaContextProvider | None = None,
    duplicate_lookup: DuplicateLookup | None = None,
) -> list[FlagRule]:
    media = media_provider or NullMediaContextProvider()
    duplicates = duplicate_lookup or NullDuplicateLookup()
    return [
        CompletenessRule(),
        VocabularyRule(),
        NonClaimRule(),
        GeoRule(),
        MediaRule(media_provider=media),
        MediaHeuristicRule(media_provider=media),
        ExifRule(media_provider=media),
        DuplicateRule(lookup=duplicates),
        FhirReadinessRule(),
        AiAssistRule(),
    ]


def sort_flags(flags: Iterable[QualityFlag]) -> list[QualityFlag]:
    """Deterministic ordering independent of dict/set iteration."""
    return sorted(
        flags,
        key=lambda f: (
            _SEVERITY_SORT.get(f.severity, 99),
            f.rule_id,
            f.code,
            f.message,
            f.flag_id,
        ),
    )
