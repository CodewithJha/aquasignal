"""Central protocol-lite field schema for FlagEngine.

Internal citizen-safe vocabulary only. Exact TemporaryOahSystem / Annex I
value-set bindings remain [VERIFY] — these keys are NOT official OAH FHIR codes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from app.domain.value_objects import CITIZEN_SAFE_FIELD_CODES, EXCLUDED_FIELD_CODES

# Re-export domain allowlists as the FlagEngine source of truth for codes.
FIELD_ALLOWLIST: frozenset[str] = CITIZEN_SAFE_FIELD_CODES
EXCLUDED_CODES: frozenset[str] = EXCLUDED_FIELD_CODES

FLAG_RULES_VERSION = "0.1.0"

# Provisional required-for-finalize sensory triad. Cardinality of other Annex I
# fields is [VERIFY] — do not treat this as confirmed OAH protocol policy.
REQUIRED_FOR_FINALIZE: frozenset[str] = frozenset({"foam", "colour", "smell"})

# Internal domain vocabularies (normalized comparison uses lowercase str).
# Values are domain-local pending IG verification — not TemporaryOahSystem codes.
_APE = frozenset({"a", "p", "e"})
_BOOLISH = frozenset({"true", "false", "yes", "no", "0", "1"})
_RIPARIAN_BINS = frozenset(
    {
        "none",
        "0-25",
        "25-50",
        "50-75",
        "75-100",
        "sparse",
        "moderate",
        "dense",
        # Verified TemporaryOahSystem RiparianVegetationValueOahVs (Phase 5 export).
        "0-20-percent",
        "21-40-percent",
        "41-60-percent",
        "61-80-percent",
        "81-100-percent",
    }
)
_FOAM = frozenset({"absent", "present", "abundant", "none"})
_COLOUR = frozenset(
    {"clear", "brown", "green", "grey", "gray", "yellow", "other", "unknown"}
)
_SMELL = frozenset(
    {"none", "mild", "strong", "sewage", "chemical", "earthy", "other", "unknown"}
)

FIELD_VOCABULARIES: Mapping[str, frozenset[str]] = {
    "macrophytes": _APE,
    "macrophytes_non_native": _BOOLISH,
    "riparian_vegetation": _RIPARIAN_BINS,
    "riparian_non_native": _BOOLISH,
    "hydromorphology": _APE,
    "foam": _FOAM,
    "colour": _COLOUR,
    "smell": _SMELL,
}

# Vegetation / cover codes that may later require bank/reach photo evidence
# when a MediaContextProvider is bound (Phase 9+ media).
VEGETATION_FIELD_CODES: frozenset[str] = frozenset(
    {
        "macrophytes",
        "macrophytes_non_native",
        "riparian_vegetation",
        "riparian_non_native",
    }
)


@dataclass(frozen=True, slots=True)
class FieldSchema:
    """Lookup helper around the centralized schema tables."""

    allowlist: frozenset[str] = FIELD_ALLOWLIST
    excluded: frozenset[str] = EXCLUDED_CODES
    required_for_finalize: frozenset[str] = REQUIRED_FOR_FINALIZE
    vocabularies: Mapping[str, frozenset[str]] = field(
        default_factory=lambda: FIELD_VOCABULARIES
    )
    vegetation_codes: frozenset[str] = VEGETATION_FIELD_CODES

    def normalize_value(self, value: object) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)) and value in (0, 1):
            return str(int(value))
        return str(value).strip().lower()

    def is_allowed_value(self, code: str, value: object) -> bool:
        vocab = self.vocabularies.get(code)
        if vocab is None:
            return False
        return self.normalize_value(value) in vocab


DEFAULT_SCHEMA = FieldSchema()
