"""Explicit ordinal maps for temporal baseline — only where vocab has order.

Isolated from detectors so mappings can be tested and versioned independently.
Uses ConfirmGate internal vocabularies (``app.flags.schema``), not OAH FHIR codes.
"""

from __future__ import annotations

from typing import Mapping

# Foam extent: absent/none < present < abundant (ConfirmGate FIELD_VOCABULARIES).
FOAM_ORDINAL: Mapping[str, int] = {
    "absent": 0,
    "none": 0,
    "present": 1,
    "abundant": 2,
}

# Macrophytes / hydromorphology A-P-E (domain-local a/p/e).
APE_ORDINAL: Mapping[str, int] = {
    "a": 0,
    "p": 1,
    "e": 2,
}

# Riparian cover — only values with an explicit cover-order relation.
# Mixed domain bins and TemporaryOahSystem percent codes are mapped separately
# within their own ladders; do not invent cross-ladder equivalence beyond order.
RIPARIAN_ORDINAL: Mapping[str, int] = {
    "none": 0,
    "sparse": 1,
    "0-25": 1,
    "0-20-percent": 1,
    "moderate": 2,
    "25-50": 2,
    "21-40-percent": 2,
    "dense": 3,
    "50-75": 3,
    "41-60-percent": 3,
    "75-100": 4,
    "61-80-percent": 4,
    "81-100-percent": 5,
}

# Field code → ordinal map. Colour/smell omitted (no protocol ordinal order).
# Boolean non-native flags omitted (binary presence, not temporal ordinal series).
ORDINAL_FIELD_MAPS: Mapping[str, Mapping[str, int]] = {
    "foam": FOAM_ORDINAL,
    "macrophytes": APE_ORDINAL,
    "hydromorphology": APE_ORDINAL,
    "riparian_vegetation": RIPARIAN_ORDINAL,
}

TEMPORAL_ORDINAL_FIELDS: frozenset[str] = frozenset(ORDINAL_FIELD_MAPS)


def to_ordinal(field_code: str, raw_value: object) -> int | None:
    """Map a protocol value to an ordinal int, or None if unmapped/invalid."""
    table = ORDINAL_FIELD_MAPS.get(field_code)
    if table is None:
        return None
    key = str(raw_value).strip().lower()
    return table.get(key)
