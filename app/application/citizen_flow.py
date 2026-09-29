"""Citizen observation lifecycle — thin orchestration over domain + flags + FHIR.

Routes call this service. FlagEngine is never instantiated in routes.
AI suggestions are optional and never authoritative.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Mapping

from app.ai.port import AiAssistPort
from app.ai.validate import suggestion_value
from app.application.ai_assist import (
    AI_UNAVAILABLE_MESSAGE,
    domain_suggestion_payload,
    merge_suggestions,
    safe_explain_flags,
    safe_suggest_enums,
)
from app.application.errors import PacketNotFound, PersistenceError
from app.application.ports import PacketRecord, ProvenanceRecord
from app.application.service import ObservationService
from app.domain.enums import ActorType, FieldSource, WorkflowState
from app.domain.errors import (
    ConfirmationBlocked,
    DomainValidationError,
    FinalizationBlocked,
    InvalidFieldValue,
    InvalidStateTransition,
    UnauthorizedDomainAction,
)
from app.domain.packet import ObservationPacket
from app.domain.provenance_port import ProvenanceIntent
from app.domain.value_objects import Actor, FieldValue, SiteRef
from app.fhir.exporter import FhirExportResult, export_bundle_with_meta
from app.fhir.validator import FhirValidatorPort, NullFhirValidator
from app.flags.schema import FLAG_RULES_VERSION

logger = logging.getLogger("confirmgate.citizen_flow")

CITIZEN_ACTOR_ID = "web-citizen"


class CitizenFlowError(Exception):
    """User-facing orchestration failure with a stable code."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class CitizenFlowService:
    """Submit → flag → correct/revalidate → confirm → finalize → FHIR export."""

    def __init__(
        self,
        observation: ObservationService,
        *,
        ai: AiAssistPort,
        fhir_validator: FhirValidatorPort | None = None,
    ) -> None:
        self._observation = observation
        self._ai = ai
        self._validator = fhir_validator or NullFhirValidator()

    @property
    def observation(self) -> ObservationService:
        return self._observation

    @property
    def flag_engine_version(self) -> str:
        return self._observation.flag_engine.version

    @property
    def ai_model_id(self) -> str:
        return getattr(self._ai, "model_id", "unknown")

    @property
    def ai_provider_name(self) -> str:
        return getattr(self._ai, "provider_name", "unknown")

    def get(self, packet_id: str) -> PacketRecord:
        return self._observation.get(packet_id)

    def list_provenance(self, packet_id: str) -> list[ProvenanceRecord]:
        return self._observation.list_provenance(packet_id)

    def submit(
        self,
        *,
        site: SiteRef,
        fields: Mapping[str, FieldValue],
        notes: str | None = None,
        photo_name: str | None = None,
        submitter_display: str = "citizen",
        author_actor_id: str = CITIZEN_ACTOR_ID,
        effective_at: datetime | None = None,
        observer_ref: str | None = None,
    ) -> PacketRecord:
        """Create packet, set fields, FlagEngine, optional AI suggestions.

        AI failure never blocks submit. Suggestions are non-authoritative until
        an explicit human Use suggestion action.
        """
        citizen = Actor(ActorType.CITIZEN, author_actor_id)
        system = Actor(ActorType.SYSTEM, "citizen-flow")
        when = effective_at or datetime.now(timezone.utc)

        packet = ObservationPacket.create(
            site,
            submitter_display=submitter_display,
            author_actor_id=author_actor_id,
            effective_at=when,
            observer_ref=observer_ref,
        )
        if notes and notes.strip():
            packet.set_notes(notes.strip(), actor=citizen)
        if fields:
            packet.replace_fields(fields, actor=citizen)

        # Deterministic FlagEngine first — AI never decides validity.
        self._observation.apply_engine_flags(packet, actor=system)

        enum_suggestions, ai_warning = safe_suggest_enums(self._ai, packet)
        explanations, explain_warning = safe_explain_flags(
            self._ai, packet, list(packet.flags)
        )
        merged = merge_suggestions(enum_suggestions, explanations)
        packed = domain_suggestion_payload(merged)
        packet.apply_suggestions(
            packed,
            actor=Actor(ActorType.AI_PROVIDER, self.ai_model_id),
            model_id=merged.model_id,
            prompt_version=merged.prompt_version,
        )
        # Revalidate so NonClaimRule can see suggestion keys (defense in depth).
        if packed:
            self._observation.apply_engine_flags(packet, actor=system)

        try:
            record = self._observation.persist_new(packet)
        except PersistenceError:
            logger.exception("submit.persist_failed", extra={"site_id": site.site_id})
            raise

        if ai_warning or explain_warning:
            try:
                self._observation.append_provenance(
                    ProvenanceIntent(
                        packet_id=packet.packet_id,
                        action="ai.unavailable",
                        actor=system,
                        after={
                            "message": AI_UNAVAILABLE_MESSAGE,
                            "provider": self.ai_provider_name,
                            "model": self.ai_model_id,
                        },
                        model_id=self.ai_model_id,
                        prompt_version=merged.prompt_version,
                        rule_engine_version=self.flag_engine_version,
                    )
                )
            except PersistenceError:
                logger.warning(
                    "submit.ai_unavailable_note_failed",
                    extra={"packet_id": packet.packet_id},
                )

        if photo_name:
            try:
                self._observation.append_provenance(
                    ProvenanceIntent(
                        packet_id=packet.packet_id,
                        action="media.noted",
                        actor=citizen,
                        after={"photo_name": photo_name},
                        model_id=self.ai_model_id,
                        rule_engine_version=self.flag_engine_version,
                    )
                )
            except PersistenceError:
                logger.warning(
                    "submit.media_note_failed",
                    extra={"packet_id": packet.packet_id},
                )

        logger.info(
            "submit.ok",
            extra={
                "packet_id": packet.packet_id,
                "site_id": site.site_id,
                "flag_count": len(packet.flags),
                "state": packet.workflow_state.value,
                "ai_model": self.ai_model_id,
                "ai_provider": self.ai_provider_name,
                "ai_available": merged.available and not (ai_warning or explain_warning),
                "rules_version": self.flag_engine_version,
            },
        )
        return record

    def accept_suggestion(
        self,
        packet_id: str,
        *,
        field: str,
        actor_id: str = CITIZEN_ACTOR_ID,
    ) -> PacketRecord:
        """Human explicitly uses an AI suggestion → field mutation + FlagEngine."""
        citizen = Actor(ActorType.CITIZEN, actor_id)
        system = Actor(ActorType.SYSTEM, "citizen-flow")
        code = field.strip().lower()

        def _mutate(packet: ObservationPacket) -> None:
            if packet.workflow_state != WorkflowState.FLAGGED:
                raise CitizenFlowError(
                    "suggestion_locked",
                    "Suggestions can only be applied while flags are open "
                    f"(current state: {packet.workflow_state.value}).",
                )
            raw = packet.suggestions.get(code)
            value = suggestion_value(raw)
            if value is None:
                raise CitizenFlowError(
                    "suggestion_missing",
                    f"No AI suggestion available for {code!r}.",
                )
            packet.set_field(
                FieldValue(
                    code=code,
                    value=value,
                    source=FieldSource.AI_SUGGESTION_ACCEPTED,
                ),
                actor=citizen,
            )
            self._observation.apply_engine_flags(packet, actor=system)

        try:
            record, _ = self._observation.mutate(packet_id, _mutate)
        except PacketNotFound:
            raise
        except CitizenFlowError:
            raise
        except (
            InvalidStateTransition,
            DomainValidationError,
            UnauthorizedDomainAction,
            InvalidFieldValue,
        ) as exc:
            raise CitizenFlowError("suggestion_rejected", str(exc)) from exc

        logger.info(
            "accept_suggestion.ok",
            extra={"packet_id": packet_id, "field": code},
        )
        return record

    def decline_suggestion(
        self,
        packet_id: str,
        *,
        field: str,
        actor_id: str = CITIZEN_ACTOR_ID,
    ) -> PacketRecord:
        """Human keeps their value — fields unchanged; provenance records decline."""
        citizen = Actor(ActorType.CITIZEN, actor_id)
        code = field.strip().lower()

        def _mutate(packet: ObservationPacket) -> None:
            if packet.workflow_state != WorkflowState.FLAGGED:
                raise CitizenFlowError(
                    "suggestion_locked",
                    "Suggestions can only be declined while flags are open "
                    f"(current state: {packet.workflow_state.value}).",
                )
            if code not in packet.suggestions:
                raise CitizenFlowError(
                    "suggestion_missing",
                    f"No AI suggestion available for {code!r}.",
                )
            remaining = {
                k: v for k, v in packet.suggestions.items() if k != code
            }
            # Fields intentionally unchanged — only clear the declined advisory.
            packet.apply_suggestions(
                remaining,
                actor=citizen,
                model_id=None,
                prompt_version=None,
            )

        try:
            record, _ = self._observation.mutate(packet_id, _mutate)
        except PacketNotFound:
            raise
        except CitizenFlowError:
            raise
        except (
            InvalidStateTransition,
            DomainValidationError,
            UnauthorizedDomainAction,
        ) as exc:
            raise CitizenFlowError("suggestion_rejected", str(exc)) from exc

        try:
            self._observation.append_provenance(
                ProvenanceIntent(
                    packet_id=packet_id,
                    action="suggestion.declined",
                    actor=citizen,
                    after={"field": code, "decision": "keep_my_value"},
                    rule_engine_version=self.flag_engine_version,
                )
            )
        except PersistenceError:
            logger.warning(
                "decline_suggestion.provenance_failed",
                extra={"packet_id": packet_id, "field": code},
            )

        logger.info(
            "decline_suggestion.ok",
            extra={"packet_id": packet_id, "field": code},
        )
        return record

    def correct(
        self,
        packet_id: str,
        *,
        fields: Mapping[str, FieldValue],
        notes: str | None = None,
        actor_id: str = CITIZEN_ACTOR_ID,
    ) -> PacketRecord:
        """Replace fields while FLAGGED, revalidate with DeterministicFlagEngine.

        Same packet_id — no duplicate packet. Stale flags are replaced.
        """
        citizen = Actor(ActorType.CITIZEN, actor_id)
        system = Actor(ActorType.SYSTEM, "citizen-flow")

        def _mutate(packet: ObservationPacket) -> None:
            if packet.workflow_state == WorkflowState.AWAITING_CONFIRM:
                raise CitizenFlowError(
                    "edit_locked",
                    "Fields are locked after the observation is ready for confirm. "
                    "Withdraw is not offered in this demo surface; submit a new "
                    "observation if you need a different site.",
                )
            if packet.workflow_state != WorkflowState.FLAGGED:
                raise CitizenFlowError(
                    "edit_not_allowed",
                    f"Corrections are only allowed while flags are open "
                    f"(current state: {packet.workflow_state.value}).",
                )
            packet.replace_fields(fields, actor=citizen)
            if notes is not None:
                packet.set_notes(notes.strip() or None, actor=citizen)
            # replace_fields cleared flags; revalidate immediately so stale flags
            # are never shown as authoritative after edit.
            self._observation.apply_engine_flags(packet, actor=system)

        try:
            record, _ = self._observation.mutate(packet_id, _mutate)
        except PacketNotFound:
            raise
        except CitizenFlowError:
            raise
        except (
            InvalidStateTransition,
            DomainValidationError,
            UnauthorizedDomainAction,
        ) as exc:
            raise CitizenFlowError("correction_rejected", str(exc)) from exc

        logger.info(
            "correct.ok",
            extra={
                "packet_id": packet_id,
                "flag_count": len(record.packet.flags),
                "state": record.packet.workflow_state.value,
            },
        )
        return record

    def confirm(self, packet_id: str, *, actor_id: str = CITIZEN_ACTOR_ID) -> PacketRecord:
        """Explicit human confirm — separate from finalize/export."""
        citizen = Actor(ActorType.CITIZEN, actor_id)
        system = Actor(ActorType.SYSTEM, "citizen-flow")

        def _mutate(packet: ObservationPacket) -> None:
            if packet.author_actor_id != actor_id:
                raise UnauthorizedDomainAction("confirm requires packet author")
            if packet.workflow_state == WorkflowState.FLAGGED:
                if packet.standing_hard_rejects():
                    raise ConfirmationBlocked(
                        "Cannot confirm while hard problems remain. "
                        "Correct the fields highlighted under Needs correction."
                    )
                packet.mark_awaiting_confirm(actor=system)
            if packet.workflow_state != WorkflowState.AWAITING_CONFIRM:
                raise CitizenFlowError(
                    "confirm_not_ready",
                    f"Confirm is available after flag evaluation "
                    f"(current state: {packet.workflow_state.value}).",
                )
            packet.confirm(actor=citizen)

        try:
            record, _ = self._observation.mutate(packet_id, _mutate)
        except PacketNotFound:
            raise
        except CitizenFlowError:
            raise
        except ConfirmationBlocked as exc:
            raise CitizenFlowError("confirm_blocked", str(exc)) from exc
        except (
            InvalidStateTransition,
            UnauthorizedDomainAction,
            DomainValidationError,
        ) as exc:
            raise CitizenFlowError("confirm_rejected", str(exc)) from exc

        logger.info(
            "confirm.ok",
            extra={"packet_id": packet_id, "state": record.packet.workflow_state.value},
        )
        return record

    def request_review(
        self,
        packet_id: str,
        *,
        reason: str | None = None,
        actor_id: str = CITIZEN_ACTOR_ID,
    ) -> PacketRecord:
        """Citizen hand-off: FLAGGED → NEEDS_REVIEW (does not auto-confirm).

        Soft-block flags alone do not force this path — explicit action only.
        """
        system = Actor(ActorType.SYSTEM, "citizen-flow")

        def _mutate(packet: ObservationPacket) -> None:
            if packet.author_actor_id != actor_id:
                raise UnauthorizedDomainAction(
                    "request_review requires the packet author"
                )
            if packet.workflow_state != WorkflowState.FLAGGED:
                raise CitizenFlowError(
                    "escalate_not_allowed",
                    f"Send to reviewer is available while flags are open "
                    f"(current state: {packet.workflow_state.value}).",
                )
            packet.request_review(
                actor=system,
                reason=reason or "citizen_requested_review",
            )

        try:
            record, _ = self._observation.mutate(packet_id, _mutate)
        except PacketNotFound:
            raise
        except CitizenFlowError:
            raise
        except (
            InvalidStateTransition,
            UnauthorizedDomainAction,
            DomainValidationError,
        ) as exc:
            raise CitizenFlowError("escalate_rejected", str(exc)) from exc

        logger.info(
            "request_review.ok",
            extra={"packet_id": packet_id, "state": record.packet.workflow_state.value},
        )
        return record

    def finalize(
        self,
        packet_id: str,
        *,
        one_health_sentence: str | None = None,
        actor_id: str = CITIZEN_ACTOR_ID,
    ) -> PacketRecord:
        """Explicit finalize — does not auto-export FHIR."""
        actor = Actor(ActorType.CITIZEN, actor_id)
        sentence = (one_health_sentence or "").strip() or None

        def _mutate(packet: ObservationPacket) -> None:
            if packet.workflow_state != WorkflowState.CONFIRMED:
                raise CitizenFlowError(
                    "finalize_not_ready",
                    "Finalize is available only after human confirm "
                    f"(current state: {packet.workflow_state.value}).",
                )
            if packet.standing_soft_blocks() or packet.standing_hard_rejects():
                raise FinalizationBlocked(
                    "Cannot finalize while blocking flags remain. "
                    "Correct fields before confirm, or see StructuralGuard reasons."
                )
            packet.finalize(actor=actor, one_health_sentence=sentence)

        try:
            record, _ = self._observation.mutate(packet_id, _mutate)
        except PacketNotFound:
            raise
        except CitizenFlowError:
            raise
        except FinalizationBlocked as exc:
            raise CitizenFlowError("finalize_blocked", str(exc)) from exc
        except (
            InvalidStateTransition,
            UnauthorizedDomainAction,
            DomainValidationError,
        ) as exc:
            raise CitizenFlowError("finalize_rejected", str(exc)) from exc

        logger.info(
            "finalize.ok",
            extra={"packet_id": packet_id, "state": record.packet.workflow_state.value},
        )
        return record

    def export_fhir(self, packet_id: str) -> tuple[PacketRecord, FhirExportResult]:
        """Export FHIR Bundle for FINALIZED packets only; record digest."""
        record = self._observation.get(packet_id)
        packet = record.packet
        if packet.workflow_state != WorkflowState.FINALIZED:
            raise CitizenFlowError(
                "export_not_finalized",
                f"FHIR export requires FINALIZED (current: {packet.workflow_state.value}). "
                "CONFIRMED alone is not enough — confirm ≠ finalize.",
            )
        result = export_bundle_with_meta(packet, validator=self._validator)

        system = Actor(ActorType.SYSTEM, "fhir-export")

        def _digest(p: ObservationPacket) -> None:
            p.record_fhir_export_digest(
                actor=system,
                bundle_hash=result.bundle_hash,
                mapper_version=result.mapper_version,
                fhir_bundle_id=result.bundle.get("id"),
            )

        try:
            record, _ = self._observation.mutate(packet_id, _digest)
        except (PacketNotFound, PersistenceError, DomainValidationError, InvalidStateTransition):
            logger.warning("export.digest_failed", extra={"packet_id": packet_id})

        logger.info(
            "export.ok",
            extra={
                "packet_id": packet_id,
                "bundle_hash": result.bundle_hash[:16],
                "mapper_version": result.mapper_version,
                "rules_version": result.rule_engine_version or FLAG_RULES_VERSION,
            },
        )
        return record, result

    def export_meta(self, result: FhirExportResult) -> dict[str, Any]:
        """Honest export metadata for the FHIR result surface."""
        entries = result.bundle.get("entry") or []
        return {
            "bundle_id": result.bundle.get("id"),
            "bundle_type": result.bundle.get("type"),
            "resource_count": len(entries),
            "bundle_hash": result.bundle_hash,
            "mapper_version": result.mapper_version,
            "rule_engine_version": result.rule_engine_version,
            "validation_status": "not_run",
            "validation_note": (
                "NullFhirValidator: structural mapper + StructuralGuard only. "
                "This is not an OAH IG validator pass."
            ),
            "profiles_claimed": [
                "LocationOah (structural)",
                "ObservationIndicatorsOah (structural, status=final)",
            ],
            "supported_export_scope": (
                "Verified coded indicators: foam, macrophytes, riparian_vegetation, "
                "hydromorphology. colour/smell as annotation only. "
                "No ObservationWithCompOah typed slices. No preliminary status."
            ),
        }
