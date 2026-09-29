"""Reviewer / curator lifecycle — separate from CitizenFlowService.

Load → domain mutation → FlagEngine revalidate on edit → persist + provenance
in one transaction. Optimistic concurrency via revision.

Auth is NOT implemented (hackathon demo actor). See docs/HITL-POLICY.md.
"""

from __future__ import annotations

import logging
from typing import Mapping

from app.application.errors import ConcurrencyConflict, PacketNotFound, PersistenceError
from app.application.ports import PacketRecord, ProvenanceRecord, ReviewQueueItem
from app.application.service import ObservationService
from app.domain.enums import ActorType, WorkflowState
from app.domain.errors import (
    ConfirmationBlocked,
    DomainValidationError,
    InvalidStateTransition,
    UnauthorizedDomainAction,
)
from app.domain.packet import ObservationPacket
from app.domain.value_objects import Actor, FieldValue

logger = logging.getLogger("confirmgate.reviewer_flow")

# Demo reviewer — no OAuth/JWT. Opaque id only; not a security boundary.
DEMO_REVIEWER_ACTOR_ID = "demo-reviewer"


class ReviewerFlowError(Exception):
    """User-facing reviewer orchestration failure with a stable code."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class ReviewerFlowService:
    """NEEDS_REVIEW worklist + accept / edit / reject. Never auto-finalizes."""

    def __init__(
        self,
        observation: ObservationService,
        *,
        reviewer_actor_id: str = DEMO_REVIEWER_ACTOR_ID,
    ) -> None:
        self._observation = observation
        self._reviewer_actor_id = reviewer_actor_id

    @property
    def observation(self) -> ObservationService:
        return self._observation

    @property
    def reviewer(self) -> Actor:
        return Actor(ActorType.REVIEWER, self._reviewer_actor_id)

    def get(self, packet_id: str) -> PacketRecord:
        return self._observation.get(packet_id)

    def list_provenance(self, packet_id: str) -> list[ProvenanceRecord]:
        return self._observation.list_provenance(packet_id)

    def list_queue(self, *, limit: int = 100) -> list[ReviewQueueItem]:
        """NEEDS_REVIEW only, oldest first (repo policy)."""
        return self._observation.list_for_review(
            states=(WorkflowState.NEEDS_REVIEW.value,),
            limit=limit,
        )

    def escalate(
        self,
        packet_id: str,
        *,
        reason: str | None = None,
        expected_revision: int | None = None,
        actor: Actor | None = None,
    ) -> PacketRecord:
        """FLAGGED → NEEDS_REVIEW via domain ``request_review`` (real path).

        Used by demos/fixtures and optional citizen hand-off. Soft-block alone
        does NOT auto-escalate (preserves Phase 6 soft vs hard distinction).
        """
        system_or_reviewer = actor or Actor(ActorType.SYSTEM, "reviewer-flow")

        def _mutate(packet: ObservationPacket) -> None:
            if packet.workflow_state != WorkflowState.FLAGGED:
                raise ReviewerFlowError(
                    "escalate_not_allowed",
                    f"Escalate requires FLAGGED (current: {packet.workflow_state.value}).",
                )
            packet.request_review(actor=system_or_reviewer, reason=reason)

        return self._run(packet_id, _mutate, expected_revision=expected_revision)

    def accept(
        self,
        packet_id: str,
        *,
        reason_codes: list[str] | None = None,
        expected_revision: int | None = None,
    ) -> PacketRecord:
        """NEEDS_REVIEW → CONFIRMED. Does NOT finalize or export FHIR."""
        reviewer = self.reviewer

        def _mutate(packet: ObservationPacket) -> None:
            if packet.workflow_state != WorkflowState.NEEDS_REVIEW:
                raise ReviewerFlowError(
                    "accept_not_ready",
                    f"Accept requires NEEDS_REVIEW (current: {packet.workflow_state.value}).",
                )
            if packet.standing_hard_rejects():
                raise ConfirmationBlocked(
                    "Cannot accept while standing hard_reject flags remain. "
                    "Edit fields and revalidate, or reject the packet."
                )
            packet.accept_review(actor=reviewer, reason_codes=reason_codes)

        record = self._run(packet_id, _mutate, expected_revision=expected_revision)
        logger.info(
            "review.accept.ok",
            extra={
                "packet_id": packet_id,
                "state": record.packet.workflow_state.value,
                "actor_id": reviewer.actor_id,
            },
        )
        return record

    def reject(
        self,
        packet_id: str,
        *,
        reason_code: str,
        explanation: str | None = None,
        expected_revision: int | None = None,
    ) -> PacketRecord:
        """NEEDS_REVIEW → REJECTED. Empty reason_code refused by domain."""
        reviewer = self.reviewer

        def _mutate(packet: ObservationPacket) -> None:
            if packet.workflow_state != WorkflowState.NEEDS_REVIEW:
                raise ReviewerFlowError(
                    "reject_not_ready",
                    f"Reject requires NEEDS_REVIEW (current: {packet.workflow_state.value}).",
                )
            packet.reject(
                actor=reviewer,
                reason_code=reason_code,
                explanation=explanation,
            )

        record = self._run(packet_id, _mutate, expected_revision=expected_revision)
        logger.info(
            "review.reject.ok",
            extra={
                "packet_id": packet_id,
                "reason_code": reason_code,
                "actor_id": reviewer.actor_id,
            },
        )
        return record

    def edit(
        self,
        packet_id: str,
        *,
        fields: Mapping[str, FieldValue],
        notes: str | None = None,
        expected_revision: int | None = None,
    ) -> PacketRecord:
        """Edit fields while NEEDS_REVIEW → DeterministicFlagEngine revalidate.

        Stays NEEDS_REVIEW. Does not dismiss flags; engine replaces the snapshot.
        Does not silently mutate a confirmation snapshot (packet is unconfirmed).
        """
        reviewer = self.reviewer
        system = Actor(ActorType.SYSTEM, "reviewer-flow")

        def _mutate(packet: ObservationPacket) -> None:
            if packet.workflow_state != WorkflowState.NEEDS_REVIEW:
                raise ReviewerFlowError(
                    "edit_not_allowed",
                    f"Reviewer edit requires NEEDS_REVIEW "
                    f"(current: {packet.workflow_state.value}).",
                )
            packet.replace_fields(fields, actor=reviewer)
            if notes is not None:
                packet.set_notes(notes.strip() or None, actor=reviewer)
            # replace_fields cleared flags; revalidate immediately.
            self._observation.apply_engine_flags(packet, actor=system)

        record = self._run(packet_id, _mutate, expected_revision=expected_revision)
        logger.info(
            "review.edit.ok",
            extra={
                "packet_id": packet_id,
                "flag_count": len(record.packet.flags),
                "state": record.packet.workflow_state.value,
            },
        )
        return record

    def _run(
        self,
        packet_id: str,
        mutator,
        *,
        expected_revision: int | None,
    ) -> PacketRecord:
        try:
            if expected_revision is None:
                record, _ = self._observation.mutate(packet_id, mutator)
            else:
                record, _ = self._observation.mutate_at_revision(
                    packet_id, expected_revision, mutator
                )
        except PacketNotFound:
            raise
        except ConcurrencyConflict as exc:
            raise ReviewerFlowError(
                "concurrency_conflict",
                "This observation changed since you opened it "
                f"(stale revision {exc.expected_revision}). Reload and try again.",
            ) from exc
        except ReviewerFlowError:
            raise
        except ConfirmationBlocked as exc:
            raise ReviewerFlowError("accept_blocked", str(exc)) from exc
        except (
            InvalidStateTransition,
            DomainValidationError,
            UnauthorizedDomainAction,
        ) as exc:
            raise ReviewerFlowError("review_rejected", str(exc)) from exc
        except PersistenceError:
            logger.exception("review.persist_failed", extra={"packet_id": packet_id})
            raise
        return record
