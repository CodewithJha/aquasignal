"""AI-assist rule boundary — Phase 3 stub; never invokes AI."""

from __future__ import annotations

from app.domain.packet import ObservationPacket
from app.domain.value_objects import QualityFlag
from app.flags.schema import FieldSchema


class AiAssistRule:
    """Placeholder so the engine registry includes the ai_assist category.

    Phase 8 may inject AI-derived *suggestion* flags via a separate path.
    This rule never calls providers and never raises hard rejects.
    """

    rule_id_prefix = "ai_assist"

    def evaluate(
        self, packet: ObservationPacket, *, schema: FieldSchema
    ) -> list[QualityFlag]:
        _ = packet, schema
        return []
