"""InvestigationCase / AnalysisRun / HumanDecision vocabulary."""

from __future__ import annotations

from enum import Enum


class CaseState(str, Enum):
    """Minimal investigation lifecycle (spike §N Phase A1)."""

    OPEN = "OPEN"
    UNDER_REVIEW = "UNDER_REVIEW"
    CLOSED = "CLOSED"
    DISMISSED = "DISMISSED"


CASE_TERMINAL_STATES: frozenset[CaseState] = frozenset(
    {CaseState.CLOSED, CaseState.DISMISSED}
)


class AnalysisRunStatus(str, Enum):
    STARTED = "STARTED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class DecisionCode(str, Enum):
    """Human case decisions — non-diagnostic ops codes."""

    OPEN = "open"
    NOTE = "note"
    DISMISS = "dismiss"
    REQUEST_MORE_EVIDENCE = "request_more_evidence"
    CONCLUDE_INSUFFICIENT = "conclude_insufficient"
    CONCLUDE_CHANGE_SUSPECTED = "conclude_change_suspected"
