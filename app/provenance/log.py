"""Append-only provenance interface (Phase 1).

No UPDATE/DELETE on events. Corrections = new events.
Mutable audit[] lists are not the long-term model.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import uuid4

from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ProvenanceEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: uuid4().hex)
    packet_id: str
    at: datetime = Field(default_factory=_now)
    actor_type: str  # citizen | reviewer | system | ai_provider
    actor_id: str = "anonymous"
    action: str
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    model_id: str | None = None
    prompt_version: str | None = None
    rule_engine_version: str | None = None
    seq: int | None = None


class ProvenanceLog(Protocol):
    def append(self, event: ProvenanceEvent) -> ProvenanceEvent:
        ...

    def list_for_packet(self, packet_id: str) -> list[ProvenanceEvent]:
        ...


class InMemoryProvenanceLog:
    """Append-only in-memory log. No mutate-in-place API."""

    def __init__(self) -> None:
        self._events: list[ProvenanceEvent] = []
        self._seq = 0

    def append(self, event: ProvenanceEvent) -> ProvenanceEvent:
        self._seq += 1
        stored = event.model_copy(update={"seq": self._seq})
        self._events.append(stored)
        return stored

    def list_for_packet(self, packet_id: str) -> list[ProvenanceEvent]:
        return [e for e in self._events if e.packet_id == packet_id]
