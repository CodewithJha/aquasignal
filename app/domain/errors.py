"""Domain errors — no HTTP status codes."""

from __future__ import annotations

from enum import Enum


class DomainError(Exception):
    """Base for ConfirmGate / AquaSignal domain failures."""


class InvalidStateTransition(DomainError):
    """Raised when a workflow transition is illegal.

    ``current`` / ``requested`` accept ConfirmGate ``WorkflowState`` or
    AquaSignal case/run status enums (any ``Enum`` with ``.value``), or raw str.
    """

    def __init__(
        self,
        current: Enum | str,
        requested: Enum | str,
        reason: str,
    ) -> None:
        self.current = current
        self.requested = requested
        self.reason = reason
        cur = current.value if isinstance(current, Enum) else current
        req = requested.value if isinstance(requested, Enum) else requested
        super().__init__(
            f"Invalid transition from {cur} to {req}: {reason}"
        )


class DomainValidationError(DomainError):
    """General domain validation failure (site, payload shape, etc.)."""


class ConfirmationBlocked(DomainError):
    """Confirm/accept blocked by standing hard flags or actor rules."""


class FinalizationBlocked(DomainError):
    """Finalize blocked (missing snapshot, soft blocks, hash mismatch, etc.)."""


class InvalidFieldValue(DomainError):
    """Field code/value rejected by domain allowlist / exclusions."""


class UnauthorizedDomainAction(DomainError):
    """Actor is not permitted to perform this domain action (e.g. AI confirm)."""
