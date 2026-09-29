"""Map domain / application / FHIR errors to citizen-facing messages."""

from __future__ import annotations

from dataclasses import dataclass

from app.application.citizen_flow import CitizenFlowError
from app.application.errors import (
    AnalysisOrchestrationError,
    ConcurrencyConflict,
    EvidenceNotEligible,
    PacketNotFound,
    PersistenceError,
    ResourceNotFound,
)
from app.application.reviewer_flow import ReviewerFlowError
from app.domain.errors import (
    ConfirmationBlocked,
    DomainValidationError,
    FinalizationBlocked,
    InvalidFieldValue,
    InvalidStateTransition,
    UnauthorizedDomainAction,
)
from app.fhir.errors import (
    FhirExportRefused,
    FhirValidationFailure,
    FhirValidatorUnavailable,
    MissingRequiredOahData,
    StructuralGuardFailure,
    UnsupportedOahMapping,
)
from app.web.forms import FormParseError


@dataclass(frozen=True, slots=True)
class UserError:
    code: str
    message: str
    http_status: int = 400


def map_exception(exc: BaseException) -> UserError:
    if isinstance(exc, (CitizenFlowError, ReviewerFlowError)):
        status = 409 if (
            exc.code.endswith("blocked")
            or "not_" in exc.code
            or exc.code == "concurrency_conflict"
        ) else 400
        return UserError(exc.code, exc.message, http_status=status)
    if isinstance(exc, ConcurrencyConflict):
        return UserError(
            "concurrency_conflict",
            "This record changed since you opened it. Reload and try again.",
            http_status=409,
        )
    if isinstance(exc, PacketNotFound):
        return UserError("not_found", "Observation not found.", http_status=404)
    if isinstance(exc, ResourceNotFound):
        return UserError("not_found", f"{exc.resource} not found.", http_status=404)
    if isinstance(exc, EvidenceNotEligible):
        return UserError("evidence_not_eligible", str(exc), http_status=409)
    if isinstance(exc, AnalysisOrchestrationError):
        return UserError("analysis_refused", str(exc), http_status=409)
    if isinstance(exc, FormParseError):
        return UserError("form_invalid", exc.message, http_status=400)
    if isinstance(exc, (InvalidFieldValue, DomainValidationError)):
        return UserError("validation", str(exc), http_status=400)
    if isinstance(exc, ConfirmationBlocked):
        return UserError("confirm_blocked", str(exc), http_status=409)
    if isinstance(exc, FinalizationBlocked):
        return UserError("finalize_blocked", str(exc), http_status=409)
    if isinstance(exc, InvalidStateTransition):
        return UserError("illegal_state", str(exc), http_status=409)
    if isinstance(exc, UnauthorizedDomainAction):
        return UserError("unauthorized", str(exc), http_status=403)
    if isinstance(exc, StructuralGuardFailure):
        return UserError(
            "structural_guard",
            f"Cannot finalize or export: {exc}",
            http_status=409,
        )
    if isinstance(exc, MissingRequiredOahData):
        return UserError(
            "missing_oah_data",
            f"Export refused — missing required data: {exc}",
            http_status=409,
        )
    if isinstance(exc, UnsupportedOahMapping):
        return UserError(
            "unsupported_mapping",
            f"Export refused — unsupported mapping: {exc}",
            http_status=409,
        )
    if isinstance(exc, FhirExportRefused):
        return UserError("fhir_refused", str(exc), http_status=409)
    if isinstance(exc, FhirValidationFailure):
        return UserError("fhir_validation_failed", str(exc), http_status=422)
    if isinstance(exc, FhirValidatorUnavailable):
        return UserError("fhir_validator_unavailable", str(exc), http_status=503)
    if isinstance(exc, PersistenceError):
        return UserError(
            "persistence",
            "Could not save the observation. Try again.",
            http_status=500,
        )
    return UserError("internal", "Unexpected error.", http_status=500)


def map_form_errors(errors: tuple[FormParseError, ...]) -> list[UserError]:
    return [UserError("form_invalid", e.message, http_status=400) for e in errors]
