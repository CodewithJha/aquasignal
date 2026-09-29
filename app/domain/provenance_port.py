"""Provenance port boundary inside the domain (no durable store).

Application / Phase 4 persistence adapts these intents to an append-only log.
Domain never imports app.provenance, FastAPI, FHIR, or AI providers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import uuid4

from app.domain.value_objects import Actor


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class ProvenanceIntent:
    """Enough structure to answer HITL audit questions once persisted."""

    packet_id: str
    action: str
    actor: Actor
    at: datetime = field(default_factory=_utc_now)
    intent_id: str = field(default_factory=lambda: uuid4().hex)
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    model_id: str | None = None
    prompt_version: str | None = None
    rule_engine_version: str | None = None

    def to_audit_dict(self) -> dict[str, Any]:
        return {
            "intent_id": self.intent_id,
            "packet_id": self.packet_id,
            "at": self.at.isoformat(),
            "actor_type": self.actor.actor_type.value,
            "actor_id": self.actor.actor_id,
            "action": self.action,
            "before": self.before,
            "after": self.after,
            "model_id": self.model_id,
            "prompt_version": self.prompt_version,
            "rule_engine_version": self.rule_engine_version,
        }


class ProvenanceSink(Protocol):
    """Optional observer. Domain remains correct if sink is a no-op."""

    def record(self, intent: ProvenanceIntent) -> None:
        ...


class NullProvenanceSink:
    def record(self, intent: ProvenanceIntent) -> None:
        return None
