"""Deterministic canonicalization of protocol-lite values before detectors run.

ConfirmGate accepts synonymous values (``foam``: ``none``/``absent``; ``colour``:
``gray``/``grey``; boolish ``yes``/``1``/``true``). Detectors compare values, so
synonyms must collapse to one canonical token first or they surface as false
contradictions. Original values stay on the ConfirmGate packet (FHIR export)
and on the persisted EvidenceItem (provenance); only the detector input is
canonicalized. Bump the version whenever the alias table changes: it is
recorded in the snapshot manifest, so it is part of the snapshot hash.

Riparian cover is intentionally not aliased: the domain bins (``0-25``...),
descriptive bins (``sparse``...) and TemporaryOahSystem percent codes
(``0-20-percent``...) are different ladders with no exact equivalence.
"""

from __future__ import annotations

from collections.abc import Mapping

VOCABULARY_CANONICALIZATION_VERSION = "vocab-canon@1"

_BOOLISH = {"yes": "true", "1": "true", "no": "false", "0": "false"}

CANONICAL_ALIASES: Mapping[str, Mapping[str, str]] = {
    "foam": {"none": "absent"},
    "colour": {"gray": "grey"},
    "macrophytes_non_native": _BOOLISH,
    "riparian_non_native": _BOOLISH,
}


def canonical_value(field_code: str, raw: object) -> str:
    if isinstance(raw, bool):
        normalized = "true" if raw else "false"
    else:
        normalized = str(raw).strip().lower()
    return CANONICAL_ALIASES.get(field_code, {}).get(normalized, normalized)


def canonicalize_fields(fields: Mapping[str, object]) -> dict[str, str]:
    return {code: canonical_value(code, value) for code, value in fields.items()}
