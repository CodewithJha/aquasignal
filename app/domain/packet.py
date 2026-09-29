"""ObservationPacket aggregate root + explicit workflow state machine.

State machine (exact — do not invent extras):
  Happy: RECEIVED → FLAGGED → AWAITING_CONFIRM → CONFIRMED → FINALIZED
  Branches: FLAGGED→REJECTED; FLAGGED→NEEDS_REVIEW;
            NEEDS_REVIEW→CONFIRMED|REJECTED; any non-terminal→WITHDRAWN

No PRELIMINARY / FHIR_PRELIMINARY states. Domain is independent of FastAPI/FHIR/AI/DB.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Mapping
from uuid import uuid4

from app.domain.enums import (
    REJECTION_REASON_CODES,
    TERMINAL_STATES,
    ActorType,
    Severity,
    WorkflowState,
)
from app.domain.errors import (
    ConfirmationBlocked,
    DomainValidationError,
    FinalizationBlocked,
    InvalidStateTransition,
    UnauthorizedDomainAction,
)
from app.domain.observer import is_observer_ref
from app.domain.provenance_port import (
    NullProvenanceSink,
    ProvenanceIntent,
    ProvenanceSink,
)
from app.domain.value_objects import (
    Actor,
    ConfirmationSnapshot,
    FieldValue,
    QualityFlag,
    SiteRef,
    field_map_hash,
    serialize_field,
    serialize_flag,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# Explicit legal edges: (from, to) → human-readable precondition summary.
# Used for documentation/tests; mutators enforce richer preconditions.
LEGAL_TRANSITIONS: frozenset[tuple[WorkflowState, WorkflowState]] = frozenset(
    {
        (WorkflowState.RECEIVED, WorkflowState.FLAGGED),
        (WorkflowState.FLAGGED, WorkflowState.AWAITING_CONFIRM),
        (WorkflowState.FLAGGED, WorkflowState.NEEDS_REVIEW),
        (WorkflowState.FLAGGED, WorkflowState.REJECTED),
        (WorkflowState.AWAITING_CONFIRM, WorkflowState.CONFIRMED),
        (WorkflowState.NEEDS_REVIEW, WorkflowState.CONFIRMED),
        (WorkflowState.NEEDS_REVIEW, WorkflowState.REJECTED),
        (WorkflowState.CONFIRMED, WorkflowState.FINALIZED),
        # withdraw from any non-terminal
        (WorkflowState.RECEIVED, WorkflowState.WITHDRAWN),
        (WorkflowState.FLAGGED, WorkflowState.WITHDRAWN),
        (WorkflowState.AWAITING_CONFIRM, WorkflowState.WITHDRAWN),
        (WorkflowState.NEEDS_REVIEW, WorkflowState.WITHDRAWN),
        (WorkflowState.CONFIRMED, WorkflowState.WITHDRAWN),
    }
)


class ObservationPacket:
    """Single visit aggregate. Confirmation is a state, not a separate type."""

    def __init__(
        self,
        *,
        site: SiteRef,
        packet_id: str | None = None,
        effective_at: datetime | None = None,
        submitter_display: str | None = None,
        author_actor_id: str = "anonymous",
        observer_ref: str | None = None,
        provenance_sink: ProvenanceSink | None = None,
    ) -> None:
        if observer_ref is not None and not is_observer_ref(observer_ref):
            raise DomainValidationError("observer_ref must be 64 lowercase hex characters")
        self._packet_id = packet_id or uuid4().hex
        self._site = site
        self._site_ref_id = site.site_id
        self._effective_at = effective_at
        self._submitter_display = submitter_display
        self._author_actor_id = author_actor_id
        self._observer_ref = observer_ref
        self._fields: dict[str, FieldValue] = {}
        self._suggestions: dict[str, Any] = {}
        self._flags: list[QualityFlag] = []
        self._workflow_state = WorkflowState.RECEIVED
        self._confirmation: ConfirmationSnapshot | None = None
        self._one_health_sentence: str | None = None
        self._fhir_bundle_id: str | None = None
        self._notes: str | None = None
        self._rule_engine_version: str | None = None
        self._provenance_intents: list[ProvenanceIntent] = []
        self._provenance_sink: ProvenanceSink = provenance_sink or NullProvenanceSink()
        self._emit(
            action="packet.created",
            actor=Actor(ActorType.SYSTEM, "domain"),
            after={
                "site_ref_id": self._site_ref_id,
                "city": self._site.city,
                "workflow_state": self._workflow_state.value,
            },
        )

    # --- factories ----------------------------------------------------------

    @classmethod
    def create(
        cls,
        site: SiteRef,
        *,
        packet_id: str | None = None,
        effective_at: datetime | None = None,
        submitter_display: str | None = None,
        author_actor_id: str = "anonymous",
        observer_ref: str | None = None,
        provenance_sink: ProvenanceSink | None = None,
    ) -> ObservationPacket:
        """Create a packet in RECEIVED. Site city must be one of five OAH cities."""
        return cls(
            site=site,
            packet_id=packet_id,
            effective_at=effective_at,
            submitter_display=submitter_display,
            author_actor_id=author_actor_id,
            observer_ref=observer_ref,
            provenance_sink=provenance_sink,
        )

    @classmethod
    def rehydrate(
        cls,
        *,
        packet_id: str,
        site: SiteRef,
        workflow_state: WorkflowState,
        author_actor_id: str = "anonymous",
        effective_at: datetime | None = None,
        submitter_display: str | None = None,
        fields: Mapping[str, FieldValue] | None = None,
        suggestions: Mapping[str, Any] | None = None,
        flags: list[QualityFlag] | tuple[QualityFlag, ...] | None = None,
        confirmation: ConfirmationSnapshot | None = None,
        notes: str | None = None,
        one_health_sentence: str | None = None,
        fhir_bundle_id: str | None = None,
        rule_engine_version: str | None = None,
        observer_ref: str | None = None,
        provenance_sink: ProvenanceSink | None = None,
    ) -> ObservationPacket:
        """Rebuild an aggregate from durable storage without emitting provenance.

        Persistence / application layer only. Does not invent workflow transitions.
        """
        if not packet_id or not str(packet_id).strip():
            raise DomainValidationError("packet_id is required for rehydrate")
        obj = object.__new__(cls)
        obj._packet_id = packet_id
        obj._site = site
        obj._site_ref_id = site.site_id
        obj._effective_at = effective_at
        obj._submitter_display = submitter_display
        obj._author_actor_id = author_actor_id
        obj._observer_ref = observer_ref if is_observer_ref(observer_ref) else None
        obj._fields = dict(fields or {})
        obj._suggestions = dict(suggestions or {})
        obj._flags = list(flags or [])
        obj._workflow_state = workflow_state
        obj._confirmation = confirmation
        obj._one_health_sentence = one_health_sentence
        obj._fhir_bundle_id = fhir_bundle_id
        obj._notes = notes
        obj._rule_engine_version = rule_engine_version
        obj._provenance_intents = []
        obj._provenance_sink = provenance_sink or NullProvenanceSink()
        return obj

    # --- read-only views ----------------------------------------------------

    @property
    def packet_id(self) -> str:
        return self._packet_id

    @property
    def site(self) -> SiteRef:
        return self._site

    @property
    def site_ref_id(self) -> str:
        return self._site_ref_id

    @property
    def effective_at(self) -> datetime | None:
        return self._effective_at

    @property
    def submitter_display(self) -> str | None:
        return self._submitter_display

    @property
    def author_actor_id(self) -> str:
        return self._author_actor_id

    @property
    def observer_ref(self) -> str | None:
        """Opaque per-browser observer reference; never enters hashes or FHIR."""
        return self._observer_ref

    @property
    def fields(self) -> Mapping[str, FieldValue]:
        return MappingProxyType(self._fields)

    @property
    def suggestions(self) -> Mapping[str, Any]:
        return MappingProxyType(self._suggestions)

    @property
    def flags(self) -> tuple[QualityFlag, ...]:
        return tuple(self._flags)

    @property
    def workflow_state(self) -> WorkflowState:
        return self._workflow_state

    @property
    def confirmation(self) -> ConfirmationSnapshot | None:
        return self._confirmation

    @property
    def one_health_sentence(self) -> str | None:
        return self._one_health_sentence

    @property
    def fhir_bundle_id(self) -> str | None:
        return self._fhir_bundle_id

    @property
    def notes(self) -> str | None:
        return self._notes

    @property
    def rule_engine_version(self) -> str | None:
        """Last FlagEngine version attached via apply_flags (snapshot, not live truth)."""
        return self._rule_engine_version

    @property
    def is_exportable(self) -> bool:
        return self._workflow_state == WorkflowState.FINALIZED

    @property
    def is_terminal(self) -> bool:
        return self._workflow_state in TERMINAL_STATES

    def standing_hard_rejects(self) -> tuple[QualityFlag, ...]:
        return tuple(f for f in self._flags if f.is_standing_hard_reject)

    def standing_soft_blocks(self) -> tuple[QualityFlag, ...]:
        return tuple(f for f in self._flags if f.is_standing_soft_block)

    def pending_provenance(self) -> tuple[ProvenanceIntent, ...]:
        return tuple(self._provenance_intents)

    def drain_provenance_intents(self) -> list[ProvenanceIntent]:
        """Hand intents to an application adapter (Phase 4 store). Clears buffer."""
        intents = list(self._provenance_intents)
        self._provenance_intents.clear()
        return intents

    # --- field / suggestion mutators ----------------------------------------

    def set_field(self, field: FieldValue, *, actor: Actor) -> None:
        """Set or replace one field. Blocked after confirmation or in terminal states.

        Allowed in RECEIVED / FLAGGED (citizen or human) and NEEDS_REVIEW (reviewer
        only). Edits clear the flag snapshot so FlagEngine must re-run.
        """
        self._assert_fields_mutable()
        self._assert_not_ai_authority(actor, action="set_field")
        self._assert_field_edit_state(actor)
        before_hash = field_map_hash(self._fields) if self._fields else None
        self._fields[field.code] = field
        if self._workflow_state in {
            WorkflowState.FLAGGED,
            WorkflowState.NEEDS_REVIEW,
        }:
            self._flags.clear()
        self._emit(
            action="fields.set",
            actor=actor,
            before={"fields_hash": before_hash},
            after={
                "fields_hash": field_map_hash(self._fields),
                "field": serialize_field(field),
            },
        )

    def replace_fields(
        self, fields: Mapping[str, FieldValue] | list[FieldValue], *, actor: Actor
    ) -> None:
        """Replace the entire field map (RECEIVED / FLAGGED / NEEDS_REVIEW).

        NEEDS_REVIEW edits require a reviewer actor (Phase 7 curator path).
        """
        self._assert_fields_mutable()
        self._assert_not_ai_authority(actor, action="replace_fields")
        self._assert_field_edit_state(actor)
        before_hash = field_map_hash(self._fields) if self._fields else None
        if isinstance(fields, Mapping):
            new_map = {k: v for k, v in fields.items()}
            for code, fv in new_map.items():
                if fv.code != code:
                    raise DomainValidationError(
                        f"field map key {code!r} does not match FieldValue.code {fv.code!r}"
                    )
        else:
            new_map = {f.code: f for f in fields}
        self._fields = new_map
        if self._workflow_state in {
            WorkflowState.FLAGGED,
            WorkflowState.NEEDS_REVIEW,
        }:
            self._flags.clear()
        self._emit(
            action="fields.replaced",
            actor=actor,
            before={"fields_hash": before_hash},
            after={"fields_hash": field_map_hash(self._fields)},
        )

    def apply_suggestions(
        self,
        suggestions: Mapping[str, Any],
        *,
        actor: Actor,
        model_id: str | None = None,
        prompt_version: str | None = None,
    ) -> None:
        """Store non-authoritative AI/system suggestions. Never copies into fields."""
        if self.is_terminal:
            raise InvalidStateTransition(
                self._workflow_state,
                self._workflow_state,
                "cannot apply suggestions on a terminal packet",
            )
        self._suggestions = dict(suggestions)
        self._emit(
            action="suggestions.applied",
            actor=actor,
            after={"suggestions": dict(suggestions)},
            model_id=model_id,
            prompt_version=prompt_version,
        )

    def set_notes(self, notes: str | None, *, actor: Actor) -> None:
        if self.is_terminal or self._workflow_state == WorkflowState.CONFIRMED:
            raise InvalidStateTransition(
                self._workflow_state,
                self._workflow_state,
                "notes are locked after confirm or terminal states",
            )
        if self._workflow_state == WorkflowState.NEEDS_REVIEW:
            if actor.actor_type != ActorType.REVIEWER:
                raise UnauthorizedDomainAction(
                    "notes while NEEDS_REVIEW require reviewer actor"
                )
        self._notes = notes
        self._emit(
            action="notes.set",
            actor=actor,
            after={"notes": notes},
        )

    def set_effective_at(self, when: datetime | None, *, actor: Actor) -> None:
        if self._workflow_state not in {
            WorkflowState.RECEIVED,
            WorkflowState.FLAGGED,
            WorkflowState.NEEDS_REVIEW,
        }:
            raise InvalidStateTransition(
                self._workflow_state,
                self._workflow_state,
                "effective_at only mutable in RECEIVED, FLAGGED, or NEEDS_REVIEW",
            )
        if self._workflow_state == WorkflowState.NEEDS_REVIEW:
            if actor.actor_type != ActorType.REVIEWER:
                raise UnauthorizedDomainAction(
                    "effective_at while NEEDS_REVIEW require reviewer actor"
                )
        self._effective_at = when
        self._emit(
            action="effective_at.set",
            actor=actor,
            after={"effective_at": when.isoformat() if when else None},
        )

    # --- flags / workflow ---------------------------------------------------

    def apply_flags(
        self,
        flags: list[QualityFlag] | tuple[QualityFlag, ...],
        *,
        actor: Actor,
        rule_engine_version: str | None = None,
    ) -> None:
        """Attach FlagEngine output and transition RECEIVED → FLAGGED.

        Re-evaluation while already FLAGGED replaces flags and stays FLAGGED.
        Re-evaluation while NEEDS_REVIEW (Phase 7 curator edit) replaces flags
        and stays NEEDS_REVIEW — no auto-accept and no invented states.
        Routing to AWAITING_CONFIRM / NEEDS_REVIEW / REJECTED is a separate step.
        """
        if actor.actor_type not in {ActorType.SYSTEM, ActorType.REVIEWER}:
            # Citizens don't raise engine flags; system (or reviewer tooling) does.
            raise UnauthorizedDomainAction(
                "apply_flags requires system or reviewer actor"
            )
        if self._workflow_state not in {
            WorkflowState.RECEIVED,
            WorkflowState.FLAGGED,
            WorkflowState.NEEDS_REVIEW,
        }:
            raise InvalidStateTransition(
                self._workflow_state,
                WorkflowState.FLAGGED,
                "apply_flags only from RECEIVED, FLAGGED, or NEEDS_REVIEW",
            )
        before = {
            "workflow_state": self._workflow_state.value,
            "flag_ids": [f.flag_id for f in self._flags],
        }
        self._flags = list(flags)
        self._rule_engine_version = rule_engine_version
        if self._workflow_state == WorkflowState.RECEIVED:
            self._workflow_state = WorkflowState.FLAGGED
        self._emit(
            action="flags.raised",
            actor=actor,
            before=before,
            after={
                "workflow_state": self._workflow_state.value,
                "flags": [serialize_flag(f) for f in self._flags],
            },
            rule_engine_version=rule_engine_version,
        )

    def mark_awaiting_confirm(self, *, actor: Actor) -> None:
        """FLAGGED → AWAITING_CONFIRM when no standing hard_reject."""
        self._require_transition(
            WorkflowState.FLAGGED,
            WorkflowState.AWAITING_CONFIRM,
            actor=actor,
            allowed_actors={ActorType.SYSTEM, ActorType.REVIEWER},
        )
        if self.standing_hard_rejects():
            raise ConfirmationBlocked(
                "cannot enter AWAITING_CONFIRM with standing non-overridden hard_reject"
            )
        self._transition(
            WorkflowState.AWAITING_CONFIRM,
            actor=actor,
            action="flags.evaluated",
            after_extra={"gate": "awaiting_confirm"},
        )

    def request_review(self, *, actor: Actor, reason: str | None = None) -> None:
        """FLAGGED → NEEDS_REVIEW (escalation)."""
        self._require_transition(
            WorkflowState.FLAGGED,
            WorkflowState.NEEDS_REVIEW,
            actor=actor,
            allowed_actors={ActorType.SYSTEM, ActorType.REVIEWER},
        )
        self._transition(
            WorkflowState.NEEDS_REVIEW,
            actor=actor,
            action="review.queued",
            after_extra={"reason": reason},
        )

    def override_flag(
        self, flag_id: str, *, reason: str, actor: Actor
    ) -> None:
        """Human override of an overridable flag (reason required)."""
        if self.is_terminal:
            raise InvalidStateTransition(
                self._workflow_state,
                self._workflow_state,
                "cannot override flags on a terminal packet",
            )
        if not actor.is_human:
            raise UnauthorizedDomainAction("only humans may override flags")
        for i, flag in enumerate(self._flags):
            if flag.flag_id == flag_id:
                updated = flag.with_override(reason=reason, actor=actor)
                self._flags[i] = updated
                self._emit(
                    action="flag.overridden",
                    actor=actor,
                    after=serialize_flag(updated),
                )
                return
        raise DomainValidationError(f"unknown flag_id {flag_id!r}")

    def confirm(self, *, actor: Actor) -> ConfirmationSnapshot:
        """AWAITING_CONFIRM → CONFIRMED. Citizen author only. Freezes snapshot."""
        if actor.is_ai:
            raise UnauthorizedDomainAction("AI cannot confirm a packet")
        if actor.actor_type != ActorType.CITIZEN:
            raise UnauthorizedDomainAction(
                "confirm requires citizen actor; reviewers use accept_review"
            )
        if actor.actor_id != self._author_actor_id:
            raise UnauthorizedDomainAction(
                "confirm requires the packet author (actor_id mismatch)"
            )
        self._require_transition(
            WorkflowState.AWAITING_CONFIRM,
            WorkflowState.CONFIRMED,
            actor=actor,
            allowed_actors={ActorType.CITIZEN},
        )
        if self.standing_hard_rejects():
            raise ConfirmationBlocked(
                "cannot confirm with standing non-overridden hard_reject"
            )
        snapshot = ConfirmationSnapshot.from_fields(self._fields, actor=actor)
        self._confirmation = snapshot
        self._transition(
            WorkflowState.CONFIRMED,
            actor=actor,
            action="human.confirmed",
            after_extra={
                "confirmation_hash": snapshot.content_hash,
                "field_codes": [f.code for f in snapshot.fields],
            },
        )
        return snapshot

    def accept_review(
        self, *, actor: Actor, reason_codes: list[str] | None = None
    ) -> ConfirmationSnapshot:
        """NEEDS_REVIEW → CONFIRMED. Reviewer only."""
        if actor.is_ai:
            raise UnauthorizedDomainAction("AI cannot accept_review / confirm")
        if actor.actor_type != ActorType.REVIEWER:
            raise UnauthorizedDomainAction("accept_review requires reviewer actor")
        self._require_transition(
            WorkflowState.NEEDS_REVIEW,
            WorkflowState.CONFIRMED,
            actor=actor,
            allowed_actors={ActorType.REVIEWER},
        )
        if self.standing_hard_rejects():
            raise ConfirmationBlocked(
                "cannot accept_review with standing non-overridden hard_reject"
            )
        snapshot = ConfirmationSnapshot.from_fields(self._fields, actor=actor)
        self._confirmation = snapshot
        self._transition(
            WorkflowState.CONFIRMED,
            actor=actor,
            action="review.accepted",
            after_extra={
                "confirmation_hash": snapshot.content_hash,
                "reason_codes": list(reason_codes or []),
            },
        )
        return snapshot

    def reject(
        self,
        *,
        actor: Actor,
        reason_code: str,
        explanation: str | None = None,
    ) -> None:
        """FLAGGED → REJECTED or NEEDS_REVIEW → REJECTED.

        ``reason_code`` must be one of :data:`REJECTION_REASON_CODES`. Empty codes
        are refused. ``explanation`` is optional free text (recommended for
        ``other``).
        """
        if actor.is_ai:
            raise UnauthorizedDomainAction("AI cannot reject")
        code = (reason_code or "").strip()
        if not code:
            raise DomainValidationError("reject reason_code is required")
        if code not in REJECTION_REASON_CODES:
            raise DomainValidationError(
                f"unknown rejection reason_code {code!r}; "
                f"allowed: {sorted(REJECTION_REASON_CODES)}"
            )
        note = (explanation or "").strip() or None
        if self._workflow_state == WorkflowState.FLAGGED:
            allowed = {ActorType.SYSTEM, ActorType.REVIEWER}
            action = "packet.rejected"
        elif self._workflow_state == WorkflowState.NEEDS_REVIEW:
            allowed = {ActorType.REVIEWER}
            action = "review.rejected"
        else:
            raise InvalidStateTransition(
                self._workflow_state,
                WorkflowState.REJECTED,
                "reject only from FLAGGED or NEEDS_REVIEW",
            )
        if actor.actor_type not in allowed:
            raise UnauthorizedDomainAction(
                f"reject from {self._workflow_state.value} not allowed for "
                f"{actor.actor_type.value}"
            )
        after: dict[str, Any] = {"reason_code": code}
        if note:
            after["explanation"] = note
        # Legacy audit key for HITL Q8 readers that expect "reason".
        after["reason"] = code if not note else f"{code}: {note}"
        self._transition(
            WorkflowState.REJECTED,
            actor=actor,
            action=action,
            after_extra=after,
        )

    def withdraw(self, *, actor: Actor, reason: str | None = None) -> None:
        """Any non-terminal → WITHDRAWN (citizen author)."""
        if actor.is_ai:
            raise UnauthorizedDomainAction("AI cannot withdraw")
        if actor.actor_type != ActorType.CITIZEN:
            raise UnauthorizedDomainAction("withdraw requires citizen actor")
        if actor.actor_id != self._author_actor_id:
            raise UnauthorizedDomainAction("withdraw requires the packet author")
        if self.is_terminal:
            raise InvalidStateTransition(
                self._workflow_state,
                WorkflowState.WITHDRAWN,
                "cannot withdraw a terminal packet",
            )
        if self._workflow_state == WorkflowState.FINALIZED:
            raise InvalidStateTransition(
                self._workflow_state,
                WorkflowState.WITHDRAWN,
                "cannot withdraw FINALIZED",
            )
        self._transition(
            WorkflowState.WITHDRAWN,
            actor=actor,
            action="packet.withdrawn",
            after_extra={"reason": reason},
        )

    def finalize(
        self,
        *,
        actor: Actor,
        one_health_sentence: str | None = None,
        fhir_bundle_id: str | None = None,
        bundle_hash: str | None = None,
        mapper_version: str | None = None,
    ) -> None:
        """CONFIRMED → FINALIZED. Requires valid confirmation snapshot; AI forbidden.

        ``bundle_hash`` / ``mapper_version`` are optional at finalize time. Prefer
        calling :meth:`record_fhir_export_digest` after ``export_bundle_with_meta``
        so HITL Q6/Q7 capture the deterministic Bundle digest (Phase 5).
        """
        if actor.is_ai:
            raise UnauthorizedDomainAction("AI cannot finalize")
        if actor.actor_type not in {ActorType.SYSTEM, ActorType.CITIZEN, ActorType.REVIEWER}:
            raise UnauthorizedDomainAction(
                f"finalize not allowed for {actor.actor_type.value}"
            )
        self._require_transition(
            WorkflowState.CONFIRMED,
            WorkflowState.FINALIZED,
            actor=actor,
            allowed_actors={ActorType.SYSTEM, ActorType.CITIZEN, ActorType.REVIEWER},
        )
        if self._confirmation is None:
            raise FinalizationBlocked("cannot finalize without a confirmation snapshot")
        if not self._confirmation.matches_fields(self._fields):
            raise FinalizationBlocked(
                "confirmation snapshot hash does not match current fields"
            )
        if self.standing_soft_blocks():
            raise FinalizationBlocked(
                "cannot finalize with standing non-overridden soft_block_finalize"
            )
        if self.standing_hard_rejects():
            raise FinalizationBlocked(
                "cannot finalize with standing non-overridden hard_reject"
            )
        self._one_health_sentence = one_health_sentence
        self._fhir_bundle_id = fhir_bundle_id or self._packet_id
        after: dict[str, Any] = {
            "confirmation_hash": self._confirmation.content_hash,
            "fhir_bundle_id": self._fhir_bundle_id,
            "one_health_sentence": self._one_health_sentence,
        }
        if bundle_hash is not None:
            after["bundle_hash"] = bundle_hash
        if mapper_version is not None:
            after["mapper_version"] = mapper_version
        self._transition(
            WorkflowState.FINALIZED,
            actor=actor,
            action="fhir.exported",
            after_extra=after,
        )

    def record_fhir_export_digest(
        self,
        *,
        actor: Actor,
        bundle_hash: str,
        mapper_version: str,
        fhir_bundle_id: str | None = None,
    ) -> None:
        """Append provenance with Bundle hash + mapper version (FINALIZED only).

        Does not change workflow state. Completes Phase 4 deferred HITL Q6/Q7
        fields when finalize ran before the Bundle was hashed. Not a FHIR
        Provenance resource — internal audit only (see docs/FHIR-SPEC.md).
        """
        if actor.is_ai:
            raise UnauthorizedDomainAction("AI cannot record FHIR export digest")
        if self._workflow_state != WorkflowState.FINALIZED:
            raise InvalidStateTransition(
                self._workflow_state,
                WorkflowState.FINALIZED,
                "record_fhir_export_digest requires FINALIZED",
            )
        if not bundle_hash or not str(bundle_hash).strip():
            raise DomainValidationError("bundle_hash is required")
        if not mapper_version or not str(mapper_version).strip():
            raise DomainValidationError("mapper_version is required")
        if fhir_bundle_id:
            self._fhir_bundle_id = fhir_bundle_id
        self._emit(
            action="fhir.export_digest",
            actor=actor,
            after={
                "bundle_hash": bundle_hash.strip(),
                "mapper_version": mapper_version.strip(),
                "fhir_bundle_id": self._fhir_bundle_id,
                "confirmation_hash": (
                    self._confirmation.content_hash if self._confirmation else None
                ),
            },
        )

    # --- internals ----------------------------------------------------------

    def _assert_fields_mutable(self) -> None:
        if self.is_terminal:
            raise InvalidStateTransition(
                self._workflow_state,
                self._workflow_state,
                "fields are immutable on terminal packets",
            )
        if self._confirmation is not None or self._workflow_state == WorkflowState.CONFIRMED:
            raise InvalidStateTransition(
                self._workflow_state,
                self._workflow_state,
                "confirmed fields cannot silently mutate",
            )

    def _assert_field_edit_state(self, actor: Actor) -> None:
        """Field writes: RECEIVED/FLAGGED any non-AI human/system; NEEDS_REVIEW reviewer only."""
        if self._workflow_state in {WorkflowState.RECEIVED, WorkflowState.FLAGGED}:
            return
        if self._workflow_state == WorkflowState.NEEDS_REVIEW:
            if actor.actor_type != ActorType.REVIEWER:
                raise UnauthorizedDomainAction(
                    "field mutation while NEEDS_REVIEW requires reviewer actor"
                )
            return
        raise InvalidStateTransition(
            self._workflow_state,
            self._workflow_state,
            "field mutation only allowed in RECEIVED, FLAGGED, or NEEDS_REVIEW "
            "(no unconfirm transition)",
        )

    def _assert_not_ai_authority(self, actor: Actor, *, action: str) -> None:
        # AI may apply suggestions via apply_suggestions; field writes must be human/import.
        if actor.is_ai:
            raise UnauthorizedDomainAction(
                f"AI cannot perform authoritative action {action!r}"
            )

    def _require_transition(
        self,
        expected_current: WorkflowState,
        target: WorkflowState,
        *,
        actor: Actor,
        allowed_actors: set[ActorType],
    ) -> None:
        if self._workflow_state != expected_current:
            raise InvalidStateTransition(
                self._workflow_state,
                target,
                f"expected current state {expected_current.value}",
            )
        if (self._workflow_state, target) not in LEGAL_TRANSITIONS:
            raise InvalidStateTransition(
                self._workflow_state,
                target,
                "transition not in legal matrix",
            )
        if actor.actor_type not in allowed_actors:
            raise UnauthorizedDomainAction(
                f"actor {actor.actor_type.value} cannot transition to {target.value}"
            )

    def _transition(
        self,
        target: WorkflowState,
        *,
        actor: Actor,
        action: str,
        after_extra: dict[str, Any] | None = None,
    ) -> None:
        if (self._workflow_state, target) not in LEGAL_TRANSITIONS:
            raise InvalidStateTransition(
                self._workflow_state,
                target,
                "transition not in legal matrix",
            )
        before = {"workflow_state": self._workflow_state.value}
        self._workflow_state = target
        after: dict[str, Any] = {"workflow_state": target.value}
        if after_extra:
            after.update(after_extra)
        self._emit(action=action, actor=actor, before=before, after=after)

    def _emit(
        self,
        *,
        action: str,
        actor: Actor,
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
        model_id: str | None = None,
        prompt_version: str | None = None,
        rule_engine_version: str | None = None,
    ) -> None:
        intent = ProvenanceIntent(
            packet_id=self._packet_id,
            action=action,
            actor=actor,
            before=before,
            after=after,
            model_id=model_id,
            prompt_version=prompt_version,
            rule_engine_version=rule_engine_version or self._rule_engine_version,
        )
        self._provenance_intents.append(intent)
        self._provenance_sink.record(intent)


def make_flag(
    *,
    rule_id: str,
    severity: Severity,
    code: str,
    message: str,
    overridable: bool = True,
    evidence_refs: list[str] | None = None,
) -> QualityFlag:
    """Test/helper factory for QualityFlag."""
    return QualityFlag(
        rule_id=rule_id,
        severity=severity,
        code=code,
        message=message,
        overridable=overridable,
        evidence_refs=tuple(evidence_refs or ()),
    )
