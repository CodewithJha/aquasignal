"""Single source of constraint for the five official OAH cities."""

from __future__ import annotations

OAH_CITIES: frozenset[str] = frozenset(
    {"Coimbra", "Benevento", "Ghent", "Oslo", "Toulouse"}
)
