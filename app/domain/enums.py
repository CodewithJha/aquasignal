"""Domain enums for ConfirmGate workflow and field/flag vocabulary."""

from __future__ import annotations

from enum import Enum


class WorkflowState(str, Enum):
    """Packet lifecycle. Terminals: FINALIZED, REJECTED, WITHDRAWN.

    App workflow state is NOT FHIR Observation.status — FHIR exists only at FINALIZED.
    """

    RECEIVED = "RECEIVED"
    FLAGGED = "FLAGGED"
    AWAITING_CONFIRM = "AWAITING_CONFIRM"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    CONFIRMED = "CONFIRMED"
    FINALIZED = "FINALIZED"
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"


TERMINAL_STATES: frozenset[WorkflowState] = frozenset(
    {
        WorkflowState.FINALIZED,
        WorkflowState.REJECTED,
        WorkflowState.WITHDRAWN,
    }
)


class Severity(str, Enum):
    """Flag severity only — no composite trust score."""

    HARD_REJECT = "hard_reject"
    SOFT_BLOCK_FINALIZE = "soft_block_finalize"
    WARN = "warn"


class ActorType(str, Enum):
    CITIZEN = "citizen"
    REVIEWER = "reviewer"
    SYSTEM = "system"
    AI_PROVIDER = "ai_provider"


class FieldSource(str, Enum):
    HUMAN = "human"
    AI_SUGGESTION_ACCEPTED = "ai_suggestion_accepted"
    IMPORT = "import"


class RejectionReasonCode(str, Enum):
    """Structured reviewer/system rejection codes (Phase 7).

    ``other`` may carry an optional free-text explanation; empty ``reason_code``
    is never valid. These are ConfirmGate ops codes — not OAH FHIR codes.
    """

    UNSUPPORTED_OBSERVATION = "unsupported_observation"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    INVALID_SITE = "invalid_site"
    PROHIBITED_CLAIM = "prohibited_claim"
    INCONSISTENT_SUBMISSION = "inconsistent_submission"
    OTHER = "other"


REJECTION_REASON_CODES: frozenset[str] = frozenset(
    c.value for c in RejectionReasonCode
)

REJECTION_REASON_LABELS: dict[str, str] = {
    RejectionReasonCode.UNSUPPORTED_OBSERVATION.value: "Unsupported observation type",
    RejectionReasonCode.INSUFFICIENT_EVIDENCE.value: "Insufficient evidence",
    RejectionReasonCode.INVALID_SITE.value: "Invalid or out-of-scope site",
    RejectionReasonCode.PROHIBITED_CLAIM.value: "Prohibited claim (non-claim policy)",
    RejectionReasonCode.INCONSISTENT_SUBMISSION.value: "Inconsistent submission",
    RejectionReasonCode.OTHER.value: "Other (explain if needed)",
}
