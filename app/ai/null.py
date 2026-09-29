"""Null AI provider — zero API keys, zero external calls."""

from __future__ import annotations

from typing import Any

from app.ai.port import FlagExplanation, PhotoAssessment, Suggestions
from app.domain.models import ObservationPacket
from app.domain.value_objects import QualityFlag


class NullAiAssist:
    """Acceptable default for ConfirmGate. Demo must work with this provider."""

    model_id: str = "null"
    provider_name: str = "null"

    def suggest_enums(
        self, packet: ObservationPacket, media: Any | None = None
    ) -> Suggestions:
        _ = packet, media
        return Suggestions(
            items={},
            suggestions=[],
            flag_explanations=[],
            model_id=self.model_id,
            provider=self.provider_name,
            notes="NullAiAssist: no suggestions. Rules/flags and human confirm remain authority.",
            available=True,
        )

    def explain_flags(
        self, packet: ObservationPacket, flags: list[QualityFlag]
    ) -> list[FlagExplanation]:
        _ = packet, flags
        return []

    def assess_photo_protocol(self, media: Any) -> PhotoAssessment:
        _ = media
        return PhotoAssessment(
            flags=[],
            model_id=self.model_id,
            notes="NullAiAssist: no photo assessment.",
        )

    def glossary(self, term: str) -> str:
        return (
            f"No glossary entry from NullAiAssist for {term!r}. "
            "Curated protocol/factsheet text lands in a later phase."
        )
