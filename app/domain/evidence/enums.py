"""Evidence source and relation vocabulary for AquaSignal Site Investigation Brief."""

from __future__ import annotations

from enum import Enum


class EvidenceSourceClass(str, Enum):
    """Where an EvidenceItem came from."""

    CONFIRMGATE_PACKET = "confirmgate_packet"
    FIXTURE = "fixture"
    PUBLIC_SERIES = "public_series"


class RelationType(str, Enum):
    """Explicit corroboration stance — never a trust score."""

    SUPPORTS = "supports"
    CONFLICTS = "conflicts"
    DUPLICATES = "duplicates"
    INSUFFICIENT = "insufficient"
