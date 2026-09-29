"""Validate AI outputs against controlled vocabulary before UI / domain apply."""

from __future__ import annotations

from typing import Any, Mapping

from app.ai.claim_safety import contains_forbidden_claim
from app.ai.port import AiSuggestion, FlagExplanation, Suggestions
from app.domain.value_objects import CITIZEN_SAFE_FIELD_CODES, EXCLUDED_FIELD_CODES, QualityFlag
from app.flags.schema import DEFAULT_SCHEMA, FIELD_VOCABULARIES

FLAG_EXPLANATIONS_KEY = "__flag_explanations__"


def _norm_key(raw: str) -> str:
    return raw.strip().lower().replace("#", "").replace("-", "_").replace(" ", "_")


def is_valid_enum_suggestion(field: str, value: object) -> bool:
    code = _norm_key(str(field))
    if code not in CITIZEN_SAFE_FIELD_CODES:
        return False
    if code in EXCLUDED_FIELD_CODES:
        return False
    return DEFAULT_SCHEMA.is_allowed_value(code, value)


def validate_ai_suggestion(
    raw: Mapping[str, Any] | AiSuggestion,
    *,
    provider: str,
    model: str,
    prompt_version: str | None,
) -> AiSuggestion | None:
    """Return a typed suggestion or None if malformed / out of vocab / prohibited."""
    try:
        if isinstance(raw, AiSuggestion):
            candidate = raw
        else:
            candidate = AiSuggestion.model_validate(
                {
                    "field": raw.get("field"),
                    "suggested_value": raw.get("suggested_value", raw.get("value")),
                    "explanation": raw.get("explanation"),
                    "model": raw.get("model", model),
                    "provider": raw.get("provider", provider),
                    "model_version": raw.get("model_version"),
                    "prompt_version": raw.get("prompt_version", prompt_version),
                    "purpose": raw.get("purpose", "enum_suggestion"),
                }
            )
    except Exception:
        return None

    field = _norm_key(candidate.field)
    if not is_valid_enum_suggestion(field, candidate.suggested_value):
        return None
    if contains_forbidden_claim(candidate.explanation):
        return None
    if candidate.purpose not in {"enum_suggestion", "categorical"}:
        return None

    normalized = DEFAULT_SCHEMA.normalize_value(candidate.suggested_value)
    return candidate.model_copy(
        update={
            "field": field,
            "suggested_value": normalized,
            "provider": provider,
            "model": model,
            "prompt_version": candidate.prompt_version or prompt_version,
        }
    )


def validate_suggestions_payload(
    payload: Mapping[str, Any] | Suggestions,
    *,
    provider: str,
    model: str,
    prompt_version: str | None,
) -> Suggestions:
    """Filter a provider payload to vocabulary-safe Suggestions."""
    if isinstance(payload, Suggestions):
        raw_list = list(payload.suggestions)
        if not raw_list and payload.items:
            raw_list = [
                {"field": k, "suggested_value": v}
                for k, v in payload.items.items()
                if k != FLAG_EXPLANATIONS_KEY
            ]
        notes = payload.notes
        available = payload.available
        flag_explanations = list(payload.flag_explanations)
    else:
        raw_list = list(payload.get("suggestions") or [])
        if not raw_list and isinstance(payload.get("items"), Mapping):
            raw_list = [
                {"field": k, "suggested_value": v}
                for k, v in payload["items"].items()
                if k != FLAG_EXPLANATIONS_KEY
            ]
        notes = payload.get("notes")
        available = bool(payload.get("available", True))
        flag_explanations = list(payload.get("flag_explanations") or [])

    validated: list[AiSuggestion] = []
    items: dict[str, Any] = {}
    for raw in raw_list:
        suggestion = validate_ai_suggestion(
            raw if isinstance(raw, Mapping) else raw,
            provider=provider,
            model=model,
            prompt_version=prompt_version,
        )
        if suggestion is None:
            continue
        # First valid suggestion per field wins (deterministic).
        if suggestion.field in items:
            continue
        validated.append(suggestion)
        items[suggestion.field] = {
            "suggested_value": suggestion.suggested_value,
            "explanation": suggestion.explanation,
            "purpose": suggestion.purpose,
            "provider": suggestion.provider,
            "model": suggestion.model,
            "model_version": suggestion.model_version,
            "prompt_version": suggestion.prompt_version,
        }

    return Suggestions(
        items=items,
        suggestions=validated,
        flag_explanations=flag_explanations,
        model_id=model,
        provider=provider,
        prompt_version=prompt_version,
        notes=notes,
        available=available,
    )


def validate_flag_explanation(
    raw: Mapping[str, Any] | FlagExplanation,
    *,
    flag: QualityFlag,
    provider: str,
    model: str,
    prompt_version: str | None,
) -> FlagExplanation | None:
    try:
        if isinstance(raw, FlagExplanation):
            candidate = raw
        else:
            explanation = str(raw.get("explanation") or "").strip()
            if not explanation:
                return None
            candidate = FlagExplanation(
                flag_id=flag.flag_id,
                rule_id=flag.rule_id,
                code=flag.code,
                severity=flag.severity.value,
                source_message=flag.message,
                explanation=explanation,
                model=model,
                provider=provider,
                prompt_version=prompt_version,
            )
    except Exception:
        return None

    if contains_forbidden_claim(candidate.explanation):
        return None
    # Freeze identity to the deterministic flag — AI cannot alter these.
    return candidate.model_copy(
        update={
            "flag_id": flag.flag_id,
            "rule_id": flag.rule_id,
            "code": flag.code,
            "severity": flag.severity.value,
            "source_message": flag.message,
            "provider": provider,
            "model": model,
            "prompt_version": prompt_version or candidate.prompt_version,
            "purpose": "flag_explain",
        }
    )


def suggestion_value(raw: Any) -> str | None:
    """Extract suggested_value from flat or structured suggestion storage."""
    if raw is None:
        return None
    if isinstance(raw, Mapping):
        val = raw.get("suggested_value", raw.get("value"))
        return str(val).strip() if val is not None and str(val).strip() else None
    text = str(raw).strip()
    return text or None


def pack_suggestions_for_domain(suggestions: Suggestions) -> dict[str, Any]:
    """Shape stored on ObservationPacket.suggestions (non-authoritative)."""
    packed = dict(suggestions.items)
    if suggestions.flag_explanations:
        packed[FLAG_EXPLANATIONS_KEY] = [
            e.model_dump() for e in suggestions.flag_explanations
        ]
    return packed


def unpack_flag_explanations(stored: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = stored.get(FLAG_EXPLANATIONS_KEY) or []
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, Mapping)]


def field_suggestion_rows(stored: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Template-friendly AI suggestion rows (excludes meta keys)."""
    rows: list[dict[str, Any]] = []
    for field, raw in sorted(stored.items()):
        if field == FLAG_EXPLANATIONS_KEY:
            continue
        value = suggestion_value(raw)
        if value is None:
            continue
        explanation = None
        provider = None
        model = None
        if isinstance(raw, Mapping):
            explanation = raw.get("explanation")
            provider = raw.get("provider")
            model = raw.get("model")
        rows.append(
            {
                "field": field,
                "suggested_value": value,
                "explanation": explanation,
                "provider": provider,
                "model": model,
                "vocab": sorted(FIELD_VOCABULARIES.get(field, ())),
            }
        )
    return rows
