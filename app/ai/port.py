"""AiAssistPort — optional suggestions only. Never authority for FHIR."""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, Field, field_validator

from app.domain.models import ObservationPacket
from app.domain.value_objects import QualityFlag


class AiSuggestion(BaseModel):
    """One bounded advisory suggestion. Never authoritative."""

    field: str
    suggested_value: str
    explanation: str | None = None
    model: str = "none"
    provider: str = "none"
    model_version: str | None = None
    prompt_version: str | None = None
    purpose: str = "enum_suggestion"

    @field_validator("field", "suggested_value", mode="before")
    @classmethod
    def _strip_required(cls, v: Any) -> str:
        text = str(v).strip() if v is not None else ""
        if not text:
            raise ValueError("field and suggested_value must be non-empty")
        return text


class FlagExplanation(BaseModel):
    """Plain-language restatement of an existing FlagEngine message.

    Cannot change severity, code, rule_id, or blocking behavior.
    """

    flag_id: str
    rule_id: str
    code: str
    severity: str
    source_message: str
    explanation: str
    model: str = "none"
    provider: str = "none"
    model_version: str | None = None
    prompt_version: str | None = None
    purpose: str = "flag_explain"


class Suggestions(BaseModel):
    """Bounded enum / glossary suggestions. Human must confirm before authority."""

    items: dict[str, Any] = Field(default_factory=dict)
    suggestions: list[AiSuggestion] = Field(default_factory=list)
    flag_explanations: list[FlagExplanation] = Field(default_factory=list)
    model_id: str = "none"
    provider: str = "none"
    prompt_version: str | None = None
    notes: str | None = None
    available: bool = True


class PhotoAssessment(BaseModel):
    """Protocol QA hints (blur, not-a-stream). Maps to flags later — not ecology scores."""

    flags: list[dict[str, Any]] = Field(default_factory=list)
    model_id: str = "none"
    notes: str | None = None


class AiAssistPort(Protocol):
    """Replaceable AI assist. Implementations must not write domain/DB/FHIR."""

    model_id: str
    provider_name: str

    def suggest_enums(
        self, packet: ObservationPacket, media: Any | None = None
    ) -> Suggestions:
        ...

    def explain_flags(
        self, packet: ObservationPacket, flags: list[QualityFlag]
    ) -> list[FlagExplanation]:
        ...

    def assess_photo_protocol(self, media: Any) -> PhotoAssessment:
        ...

    def glossary(self, term: str) -> str:
        ...
