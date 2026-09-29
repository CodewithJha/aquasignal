"""Optional HTTP AiAssistPort — OpenAI-compatible chat completions.

Never imported at pytest default path with network. Composition selects this
only when AI_PROVIDER is set and a key is present; otherwise NullAiAssist.
"""

from __future__ import annotations

from typing import Any

from app.ai.errors import AiAssistSchemaError, AiAssistTimeout, AiAssistUnavailable
from app.ai.http_chat import HttpPost, JsonChatClient, provider_label
from app.ai.port import FlagExplanation, PhotoAssessment, Suggestions
from app.ai.prompts import (
    ENUM_SUGGEST_SYSTEM,
    FLAG_EXPLAIN_PROMPT_VERSION,
    FLAG_EXPLAIN_SYSTEM,
    PROMPT_VERSION,
    build_enum_suggest_user_payload,
    build_flag_explain_user_payload,
)
from app.ai.validate import validate_flag_explanation, validate_suggestions_payload
from app.domain.models import ObservationPacket
from app.domain.value_objects import QualityFlag
from app.flags.schema import DEFAULT_SCHEMA, FIELD_VOCABULARIES

class OptionalProviderAiAssist:
    """Advisory-only HTTP provider. Failures must not block core flow."""

    provider_name: str = "openai"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float = 8.0,
        base_url: str = "https://api.openai.com/v1",
        http_post: HttpPost | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("api_key required for OptionalProviderAiAssist")
        self.model_id = model
        self.provider_name = provider_label(base_url)
        self._client = JsonChatClient(
            api_key=api_key,
            model=model,
            timeout_seconds=timeout_seconds,
            base_url=base_url,
            http_post=http_post,
        )

    def suggest_enums(
        self, packet: ObservationPacket, media: Any | None = None
    ) -> Suggestions:
        _ = media
        empty = [c for c in FIELD_VOCABULARIES if c not in packet.fields]
        if not empty:
            return Suggestions(
                model_id=self.model_id,
                provider=self.provider_name,
                prompt_version=PROMPT_VERSION,
                notes="No empty categorical fields to suggest.",
            )

        vocab = {c: sorted(FIELD_VOCABULARIES[c]) for c in empty}
        fields = {
            code: DEFAULT_SCHEMA.normalize_value(fv.value)
            for code, fv in packet.fields.items()
        }
        user = build_enum_suggest_user_payload(
            fields=fields, empty_fields=empty, vocabularies=vocab
        )
        content = self._chat_json(
            system=ENUM_SUGGEST_SYSTEM,
            user=user,
            purpose="enum_suggestion",
        )
        return validate_suggestions_payload(
            content if isinstance(content, dict) else {},
            provider=self.provider_name,
            model=self.model_id,
            prompt_version=PROMPT_VERSION,
        )

    def explain_flags(
        self, packet: ObservationPacket, flags: list[QualityFlag]
    ) -> list[FlagExplanation]:
        _ = packet
        out: list[FlagExplanation] = []
        # Bound work — explain at most a few standing flags, and stop at the
        # first timeout/outage so one submit waits at most one extra timeout.
        for flag in flags[:5]:
            user = build_flag_explain_user_payload(
                flag_id=flag.flag_id,
                rule_id=flag.rule_id,
                code=flag.code,
                severity=flag.severity.value,
                message=flag.message,
            )
            try:
                content = self._chat_json(
                    system=FLAG_EXPLAIN_SYSTEM,
                    user=user,
                    purpose="flag_explain",
                )
            except (AiAssistTimeout, AiAssistUnavailable):
                break
            except AiAssistSchemaError:
                continue
            if not isinstance(content, dict):
                continue
            explained = validate_flag_explanation(
                content,
                flag=flag,
                provider=self.provider_name,
                model=self.model_id,
                prompt_version=FLAG_EXPLAIN_PROMPT_VERSION,
            )
            if explained is not None:
                out.append(explained)
        return out

    def assess_photo_protocol(self, media: Any) -> PhotoAssessment:
        _ = media
        return PhotoAssessment(
            flags=[],
            model_id=self.model_id,
            notes="Photo AI not enabled in Phase 8 — media bytes pipeline deferred.",
        )

    def glossary(self, term: str) -> str:
        return (
            f"No live glossary for {term!r} from OptionalProviderAiAssist. "
            "Use curated protocol text."
        )

    def _chat_json(
        self, *, system: str, user: dict[str, Any], purpose: str
    ) -> dict[str, Any]:
        return self._client.chat_json(system=system, user=user, purpose=purpose)
