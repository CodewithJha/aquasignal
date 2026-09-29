"""Narrow ports for FlagEngine integrations that Phase 3 does not implement.

Media context, EXIF summaries, and duplicate lookup stay out of the engine core.
Null/default providers make rules safely no-op when data is unavailable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.domain.packet import ObservationPacket


@dataclass(frozen=True, slots=True)
class MediaAssetSummary:
    """Deterministic media metadata visible to FlagEngine — not raw bytes."""

    asset_id: str
    content_type: str
    byte_size: int | None = None
    width: int | None = None
    height: int | None = None
    sha256: str | None = None
    claimed_lat: float | None = None
    claimed_lon: float | None = None
    exif_lat: float | None = None
    exif_lon: float | None = None
    exif_available: bool = False


@dataclass(frozen=True, slots=True)
class MediaContext:
    """Media evidence available for a packet.

    ``bound=False`` means the media subsystem is not wired yet — rules must
    not invent blur/pathogen/quality flags from absence of binding.
    """

    bound: bool
    assets: tuple[MediaAssetSummary, ...] = ()


class MediaContextProvider(Protocol):
    def for_packet(self, packet: ObservationPacket) -> MediaContext:
        ...


class NullMediaContextProvider:
    """Phase 3 default: media layer not bound → media/EXIF rules stay quiet."""

    def for_packet(self, packet: ObservationPacket) -> MediaContext:
        return MediaContext(bound=False, assets=())


@dataclass(frozen=True, slots=True)
class DuplicateMatch:
    other_packet_id: str
    reason: str


class DuplicateLookup(Protocol):
    def find_duplicates(self, packet: ObservationPacket) -> tuple[DuplicateMatch, ...]:
        ...


class NullDuplicateLookup:
    """Phase 3 default: no persistence → no duplicate matches."""

    def find_duplicates(self, packet: ObservationPacket) -> tuple[DuplicateMatch, ...]:
        return ()
