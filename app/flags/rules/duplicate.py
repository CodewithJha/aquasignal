"""Duplicate detection — deterministic lookup port only; no embeddings/AI."""

from __future__ import annotations

from app.domain.enums import Severity
from app.domain.packet import ObservationPacket
from app.domain.value_objects import QualityFlag
from app.flags.ports import DuplicateLookup, NullDuplicateLookup
from app.flags.rules.base import build_flag
from app.flags.schema import FieldSchema


class DuplicateRule:
    rule_id_prefix = "duplicate"

    def __init__(self, lookup: DuplicateLookup | None = None) -> None:
        self._lookup = lookup or NullDuplicateLookup()

    def evaluate(
        self, packet: ObservationPacket, *, schema: FieldSchema
    ) -> list[QualityFlag]:
        _ = schema
        matches = self._lookup.find_duplicates(packet)
        flags: list[QualityFlag] = []
        for match in matches:
            flags.append(
                build_flag(
                    rule_id="duplicate.identity_match",
                    severity=Severity.WARN,
                    code="DUPLICATE_CANDIDATE",
                    message=(
                        f"Possible duplicate of packet {match.other_packet_id}: "
                        f"{match.reason}"
                    ),
                    evidence_refs=(
                        f"duplicate.{match.other_packet_id}",
                        "packet.identity",
                    ),
                )
            )
        return flags
