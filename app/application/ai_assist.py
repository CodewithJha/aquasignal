"""Safe AI orchestration helpers — never raise into citizen submit path."""

from __future__ import annotations

import logging
from typing import Any

from app.ai.errors import AiAssistError
from app.ai.port import AiAssistPort, FlagExplanation, Suggestions
from app.ai.prompts import PROMPT_VERSION
from app.ai.validate import (
    pack_suggestions_for_domain,
    validate_flag_explanation,
    validate_suggestions_payload,
)
from app.domain.packet import ObservationPacket
from app.domain.value_objects import QualityFlag

logger = logging.getLogger("confirmgate.ai.orchestration")

AI_UNAVAILABLE_MESSAGE = "AI assistance unavailable"


def safe_suggest_enums(
    ai: AiAssistPort, packet: ObservationPacket, media: Any | None = None
) -> tuple[Suggestions, str | None]:
    """Call suggest_enums; on any failure return empty + user message."""
    try:
        raw = ai.suggest_enums(packet, media)
        provider = getattr(ai, "provider_name", getattr(raw, "provider", "unknown"))
        model = getattr(ai, "model_id", raw.model_id)
        validated = validate_suggestions_payload(
            raw,
            provider=str(provider),
            model=str(model),
            prompt_version=raw.prompt_version or PROMPT_VERSION,
        )
        return validated, None
    except AiAssistError as exc:
        logger.warning(
            "ai.suggest_unavailable",
            extra={"error": type(exc).__name__, "model": getattr(ai, "model_id", None)},
        )
        return (
            Suggestions(
                model_id=getattr(ai, "model_id", "unavailable"),
                provider=getattr(ai, "provider_name", "unavailable"),
                available=False,
                notes=AI_UNAVAILABLE_MESSAGE,
            ),
            AI_UNAVAILABLE_MESSAGE,
        )
    except Exception as exc:
        logger.warning(
            "ai.suggest_error",
            extra={"error": type(exc).__name__, "model": getattr(ai, "model_id", None)},
        )
        return (
            Suggestions(
                model_id=getattr(ai, "model_id", "unavailable"),
                provider=getattr(ai, "provider_name", "unavailable"),
                available=False,
                notes=AI_UNAVAILABLE_MESSAGE,
            ),
            AI_UNAVAILABLE_MESSAGE,
        )


def safe_explain_flags(
    ai: AiAssistPort,
    packet: ObservationPacket,
    flags: list[QualityFlag],
) -> tuple[list[FlagExplanation], str | None]:
    if not flags:
        return [], None
    explain = getattr(ai, "explain_flags", None)
    if explain is None:
        return [], None
    try:
        raw_list = explain(packet, flags)
        provider = getattr(ai, "provider_name", "unknown")
        model = getattr(ai, "model_id", "unknown")
        out: list[FlagExplanation] = []
        by_id = {f.flag_id: f for f in flags}
        for item in raw_list or []:
            flag = by_id.get(getattr(item, "flag_id", None) or "")
            if flag is None and isinstance(item, dict):
                flag = by_id.get(str(item.get("flag_id") or ""))
            if flag is None:
                continue
            validated = validate_flag_explanation(
                item if not hasattr(item, "model_dump") else item,
                flag=flag,
                provider=str(provider),
                model=str(model),
                prompt_version=getattr(item, "prompt_version", None),
            )
            if validated is not None:
                out.append(validated)
        return out, None
    except AiAssistError:
        return [], AI_UNAVAILABLE_MESSAGE
    except Exception:
        logger.warning(
            "ai.explain_error",
            extra={"model": getattr(ai, "model_id", None)},
        )
        return [], AI_UNAVAILABLE_MESSAGE


def merge_suggestions(
    enum_suggestions: Suggestions, explanations: list[FlagExplanation]
) -> Suggestions:
    return enum_suggestions.model_copy(
        update={"flag_explanations": list(explanations)}
    )


def domain_suggestion_payload(suggestions: Suggestions) -> dict[str, Any]:
    return pack_suggestions_for_domain(suggestions)
