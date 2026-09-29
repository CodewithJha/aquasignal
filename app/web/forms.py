"""Form adapters — multipart/form → domain FieldValue map.

Human-readable labels live here; FHIR jargon stays out of citizen forms.
Unsupported / excluded codes are rejected before domain write.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from app.domain.errors import DomainValidationError, InvalidFieldValue
from app.domain.enums import FieldSource
from app.domain.value_objects import EXCLUDED_FIELD_CODES, FieldValue
from app.flags.schema import DEFAULT_SCHEMA, FIELD_VOCABULARIES, REQUIRED_FOR_FINALIZE

# Form field name → domain code (1:1 for protocol-lite).
FORM_FIELD_CODES: tuple[str, ...] = (
    "macrophytes",
    "macrophytes_non_native",
    "riparian_vegetation",
    "riparian_non_native",
    "hydromorphology",
    "foam",
    "colour",
    "smell",
)

FIELD_LABELS: dict[str, str] = {
    "macrophytes": "Aquatic plants (macrophytes)",
    "macrophytes_non_native": "Non-native aquatic plants seen?",
    "riparian_vegetation": "Bank vegetation cover",
    "riparian_non_native": "Non-native bank plants seen?",
    "hydromorphology": "Stream channel / bank alteration",
    "foam": "Foam on the water",
    "colour": "Water colour",
    "smell": "Smell near the water",
    "notes": "Notes for context (not a lab result)",
    "photo": "Photo evidence (optional)",
    "site": "Observation site",
}

# Value shown in <option> → stored domain value
FIELD_OPTIONS: dict[str, tuple[tuple[str, str], ...]] = {
    "macrophytes": (
        ("", "— select —"),
        ("a", "Absent"),
        ("p", "Present"),
        ("e", "Extensive"),
    ),
    "macrophytes_non_native": (
        ("", "— select —"),
        ("false", "No"),
        ("true", "Yes"),
    ),
    "riparian_vegetation": (
        ("", "— select —"),
        ("0-20-percent", "0–20%"),
        ("21-40-percent", "21–40%"),
        ("41-60-percent", "41–60%"),
        ("61-80-percent", "61–80%"),
        ("81-100-percent", "81–100%"),
    ),
    "riparian_non_native": (
        ("", "— select —"),
        ("false", "No"),
        ("true", "Yes"),
    ),
    "hydromorphology": (
        ("", "— select —"),
        ("a", "Absent / natural"),
        ("p", "Present"),
        ("e", "Extensive"),
    ),
    "foam": (
        ("", "— select —"),
        ("absent", "Absent"),
        ("present", "Present"),
        ("abundant", "Abundant"),
    ),
    "colour": (
        ("", "— select —"),
        ("clear", "Clear"),
        ("brown", "Brown"),
        ("green", "Green"),
        ("grey", "Grey"),
        ("yellow", "Yellow"),
        ("other", "Other"),
        ("unknown", "Unknown"),
    ),
    "smell": (
        ("", "— select —"),
        ("none", "None"),
        ("mild", "Mild"),
        ("strong", "Strong"),
        ("earthy", "Earthy"),
        ("sewage", "Sewage-like"),
        ("chemical", "Chemical"),
        ("other", "Other"),
        ("unknown", "Unknown"),
    ),
}


@dataclass(frozen=True, slots=True)
class FormParseError:
    field: str
    message: str


@dataclass(frozen=True, slots=True)
class ParsedSubmission:
    site_id: str
    fields: dict[str, FieldValue]
    notes: str | None
    photo_name: str | None
    errors: tuple[FormParseError, ...]

    @property
    def ok(self) -> bool:
        return not self.errors


def label_for(code: str) -> str:
    return FIELD_LABELS.get(code, code.replace("_", " ").title())


def options_for(code: str) -> tuple[tuple[str, str], ...]:
    return FIELD_OPTIONS.get(code, (("", "—"),))


def form_catalog() -> list[dict[str, Any]]:
    """Template-friendly field descriptors (no FHIR terms)."""
    rows: list[dict[str, Any]] = []
    required = REQUIRED_FOR_FINALIZE
    for code in FORM_FIELD_CODES:
        rows.append(
            {
                "code": code,
                "label": label_for(code),
                "options": [
                    {"value": v, "label": lab} for v, lab in options_for(code)
                ],
                "required_for_finalize": code in required,
                "help": _help_text(code),
            }
        )
    return rows


def _help_text(code: str) -> str:
    if code in REQUIRED_FOR_FINALIZE:
        return "Needed before finalize (sensory check)."
    if code.startswith("macrophytes") or code.startswith("riparian"):
        return "Optional vegetation note."
    if code == "hydromorphology":
        return "Optional channel/bank alteration note."
    return ""


def parse_submission(
    form: Mapping[str, Any],
    *,
    photo_filename: str | None = None,
    require_site: bool = True,
) -> ParsedSubmission:
    """Parse upload/correct form. Rejects unsupported and excluded values."""
    errors: list[FormParseError] = []
    site_id = str(form.get("site") or form.get("city") or "").strip().lower()
    if require_site and not site_id:
        errors.append(FormParseError("site", "Choose one of the five OAH sites."))

    fields: dict[str, FieldValue] = {}
    for code in FORM_FIELD_CODES:
        raw = form.get(code)
        if raw is None:
            continue
        text = str(raw).strip()
        if not text:
            continue
        lowered = code.lower()
        if lowered in EXCLUDED_FIELD_CODES:
            errors.append(
                FormParseError(
                    code,
                    f"{label_for(code)} is not allowed on the citizen form.",
                )
            )
            continue
        if code not in FIELD_VOCABULARIES:
            errors.append(
                FormParseError(code, f"Unsupported field {label_for(code)}.")
            )
            continue
        if not DEFAULT_SCHEMA.is_allowed_value(code, text):
            errors.append(
                FormParseError(
                    code,
                    f"Unsupported value for {label_for(code)}. "
                    "Choose an option from the list.",
                )
            )
            continue
        try:
            fields[code] = FieldValue(
                code=code,
                value=DEFAULT_SCHEMA.normalize_value(text),
                source=FieldSource.HUMAN,
            )
        except (InvalidFieldValue, DomainValidationError) as exc:
            errors.append(FormParseError(code, str(exc)))

    # Reject any sneaky excluded keys posted by a modified client.
    for key in form:
        k = str(key).strip().lower()
        if k in EXCLUDED_FIELD_CODES:
            errors.append(
                FormParseError(
                    k,
                    f"{k!r} is excluded from citizen protocol-lite storage.",
                )
            )

    notes_raw = form.get("notes")
    notes = str(notes_raw).strip() if notes_raw else None
    if notes == "":
        notes = None

    return ParsedSubmission(
        site_id=site_id,
        fields=fields,
        notes=notes,
        photo_name=photo_filename or None,
        errors=tuple(errors),
    )


def fields_from_packet(fields: Mapping[str, FieldValue]) -> dict[str, str]:
    """Current values for form redisplay."""
    return {code: str(fv.value) for code, fv in fields.items()}
