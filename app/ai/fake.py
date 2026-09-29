"""FakeAiAssist — offline deterministic suggestions for tests and local demos.

No network. Suggestions are advisory only and vocabulary-bounded.
Does not invent ecological health, pathogens, or trust scores.
"""

from __future__ import annotations

from typing import Any

from app.ai.port import FlagExplanation, PhotoAssessment, Suggestions
from app.ai.prompts import FLAG_EXPLAIN_PROMPT_VERSION, PROMPT_VERSION
from app.ai.validate import validate_suggestions_payload
from app.domain.models import ObservationPacket
from app.domain.value_objects import QualityFlag
from app.flags.schema import DEFAULT_SCHEMA, FIELD_VOCABULARIES

# Conservative fill-ins for empty sensory fields only — not ecology inference.
_EMPTY_FIELD_DEFAULTS: dict[str, str] = {
    "foam": "absent",
    "colour": "unknown",
    "smell": "unknown",
}


class FakeAiAssist:
    """Deterministic offline provider. Selected via AI_PROVIDER=fake or tests."""

    model_id: str = "fake-v1"
    provider_name: str = "fake"
    model_version: str = "1"

    def __init__(
        self,
        *,
        preset: dict[str, str] | None = None,
        fail: bool = False,
        timeout: bool = False,
    ) -> None:
        self._preset = dict(preset or {})
        self._fail = fail
        self._timeout = timeout

    def suggest_enums(
        self, packet: ObservationPacket, media: Any | None = None
    ) -> Suggestions:
        _ = media
        if self._timeout:
            from app.ai.errors import AiAssistTimeout

            raise AiAssistTimeout("fake timeout")
        if self._fail:
            from app.ai.errors import AiAssistUnavailable

            raise AiAssistUnavailable("fake unavailable")

        raw: list[dict[str, Any]] = []
        for code, value in self._preset.items():
            raw.append(
                {
                    "field": code,
                    "suggested_value": value,
                    "explanation": (
                        f"Offline fake suggestion for {code}. "
                        "Review before using — AI is not authority."
                    ),
                }
            )

        if not raw:
            for code, default in _EMPTY_FIELD_DEFAULTS.items():
                if code in packet.fields:
                    continue
                if code not in FIELD_VOCABULARIES:
                    continue
                raw.append(
                    {
                        "field": code,
                        "suggested_value": default,
                        "explanation": (
                            f"You left {code} blank. Optional fake suggestion "
                            f"'{default}' — verify visually; do not treat as truth."
                        ),
                    }
                )

        return validate_suggestions_payload(
            {"suggestions": raw},
            provider=self.provider_name,
            model=self.model_id,
            prompt_version=PROMPT_VERSION,
        )

    def explain_flags(
        self, packet: ObservationPacket, flags: list[QualityFlag]
    ) -> list[FlagExplanation]:
        _ = packet
        if self._fail or self._timeout:
            return []
        out: list[FlagExplanation] = []
        for flag in flags:
            out.append(
                FlagExplanation(
                    flag_id=flag.flag_id,
                    rule_id=flag.rule_id,
                    code=flag.code,
                    severity=flag.severity.value,
                    source_message=flag.message,
                    explanation=(
                        f"Deterministic flag ({flag.severity.value}): {flag.message} "
                        "This explanation does not change severity, code, or blocking."
                    ),
                    model=self.model_id,
                    provider=self.provider_name,
                    model_version=self.model_version,
                    prompt_version=FLAG_EXPLAIN_PROMPT_VERSION,
                )
            )
        return out

    def assess_photo_protocol(self, media: Any) -> PhotoAssessment:
        _ = media
        return PhotoAssessment(
            flags=[],
            model_id=self.model_id,
            notes="FakeAiAssist: photo assessment intentionally empty (no image AI).",
        )

    def glossary(self, term: str) -> str:
        return (
            f"Fake glossary stub for {term!r}. "
            "Curated protocol text is preferred over model prose."
        )


def empty_fields_vocab_slice(packet: ObservationPacket) -> dict[str, list[str]]:
    """Helper for provider prompts — vocab for empty allowlisted fields only."""
    out: dict[str, list[str]] = {}
    for code, vocab in FIELD_VOCABULARIES.items():
        if code in packet.fields:
            continue
        out[code] = sorted(vocab)
    return out


def current_field_map(packet: ObservationPacket) -> dict[str, str]:
    return {
        code: DEFAULT_SCHEMA.normalize_value(fv.value)
        for code, fv in packet.fields.items()
    }
