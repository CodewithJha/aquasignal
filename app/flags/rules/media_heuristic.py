"""Media heuristic rules — deterministic only; no CV / AI / fake blur scoring."""

from __future__ import annotations

from app.domain.packet import ObservationPacket
from app.domain.value_objects import QualityFlag
from app.flags.ports import MediaContextProvider, NullMediaContextProvider
from app.flags.schema import FieldSchema


class MediaHeuristicRule:
    """Phase 3: no image-quality signal exists in-domain → safe no-op.

    When a future provider exposes deterministic heuristic metadata (not AI),
    this rule can evaluate it without changing FlagEngine architecture.
    """

    rule_id_prefix = "media_heuristic"

    def __init__(
        self, media_provider: MediaContextProvider | None = None
    ) -> None:
        self._media = media_provider or NullMediaContextProvider()

    def evaluate(
        self, packet: ObservationPacket, *, schema: FieldSchema
    ) -> list[QualityFlag]:
        # Explicitly discard context: heuristics require signals we do not have.
        _ = self._media.for_packet(packet)
        _ = schema
        return []
