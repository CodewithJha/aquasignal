"""HumanDecision — authoritative case decision; AI cannot create."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from app.domain.errors import DomainValidationError, UnauthorizedDomainAction
from app.domain.investigation.enums import DecisionCode
from app.domain.value_objects import Actor


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class HumanDecision:
    """Case-level human authority record. Never emitted by AI as authoritative."""

    decision_id: str
    case_id: str
    actor: Actor
    decided_at: datetime
    decision_code: DecisionCode
    rationale: str
    linked_signal_ids: tuple[str, ...]

    @classmethod
    def create(
        cls,
        *,
        actor: Actor,
        decision_code: DecisionCode,
        rationale: str,
        linked_signal_ids: tuple[str, ...] | list[str],
        case_id: str,
        decided_at: datetime | None = None,
        decision_id: str | None = None,
    ) -> HumanDecision:
        if actor.is_ai or not actor.is_human:
            raise UnauthorizedDomainAction(
                "AI/system cannot create an authoritative HumanDecision"
            )
        if not rationale.strip():
            raise DomainValidationError("rationale is required")
        if not case_id.strip():
            raise DomainValidationError("case_id is required")
        return cls(
            decision_id=decision_id or f"dec_{uuid4().hex[:12]}",
            case_id=case_id.strip(),
            actor=actor,
            decided_at=decided_at or _utc_now(),
            decision_code=decision_code,
            rationale=rationale.strip(),
            linked_signal_ids=tuple(linked_signal_ids),
        )
