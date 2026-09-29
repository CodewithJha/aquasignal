"""InvestigationCase — human-owned site investigation container."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.domain.errors import (
    DomainValidationError,
    InvalidStateTransition,
    UnauthorizedDomainAction,
)
from app.domain.investigation.decision import HumanDecision
from app.domain.investigation.enums import CASE_TERMINAL_STATES, CaseState
from app.domain.signal.value_objects import TimeWindow
from app.domain.value_objects import Actor, SiteRef


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


LEGAL_CASE_TRANSITIONS: frozenset[tuple[CaseState, CaseState]] = frozenset(
    {
        (CaseState.OPEN, CaseState.UNDER_REVIEW),
        (CaseState.UNDER_REVIEW, CaseState.CLOSED),
        (CaseState.OPEN, CaseState.DISMISSED),
        (CaseState.UNDER_REVIEW, CaseState.DISMISSED),
    }
)


class InvestigationCase:
    """Minimal case lifecycle: OPEN → UNDER_REVIEW → CLOSED | DISMISSED.

    Conclusions require a HumanDecision. Signals may exist without a case.
    """

    def __init__(
        self,
        *,
        case_id: str,
        site: SiteRef,
        window: TimeWindow,
        analysis_run_id: str,
        signal_ids: tuple[str, ...],
        reproducibility_ref: str,
        opened_at: datetime,
        state: CaseState = CaseState.OPEN,
        decision_ids: tuple[str, ...] = (),
    ) -> None:
        self._case_id = case_id
        self._site = site
        self._window = window
        self._analysis_run_id = analysis_run_id
        self._signal_ids = signal_ids
        self._decision_ids: list[str] = list(decision_ids)
        self._reproducibility_ref = reproducibility_ref
        self._opened_at = opened_at
        self._state = state

    @classmethod
    def open(
        cls,
        *,
        site: SiteRef,
        window: TimeWindow,
        analysis_run_id: str,
        signal_ids: tuple[str, ...] | list[str],
        reproducibility_ref: str,
        opened_by: Actor,
        opened_at: datetime | None = None,
        case_id: str | None = None,
    ) -> InvestigationCase:
        if not opened_by.is_human:
            raise UnauthorizedDomainAction(
                "only a human actor may open an InvestigationCase"
            )
        if not analysis_run_id.strip():
            raise DomainValidationError("analysis_run_id is required")
        if not reproducibility_ref.strip():
            raise DomainValidationError("reproducibility_ref is required")
        return cls(
            case_id=case_id or f"case_{uuid4().hex[:12]}",
            site=site,
            window=window,
            analysis_run_id=analysis_run_id.strip(),
            signal_ids=tuple(signal_ids),
            reproducibility_ref=reproducibility_ref.strip(),
            opened_at=opened_at or _utc_now(),
        )

    @property
    def case_id(self) -> str:
        return self._case_id

    @property
    def site(self) -> SiteRef:
        return self._site

    @property
    def window(self) -> TimeWindow:
        return self._window

    @property
    def state(self) -> CaseState:
        return self._state

    @property
    def analysis_run_id(self) -> str:
        return self._analysis_run_id

    @property
    def signal_ids(self) -> tuple[str, ...]:
        return self._signal_ids

    @property
    def decision_ids(self) -> tuple[str, ...]:
        return tuple(self._decision_ids)

    @property
    def reproducibility_ref(self) -> str:
        return self._reproducibility_ref

    @property
    def opened_at(self) -> datetime:
        return self._opened_at

    @property
    def is_terminal(self) -> bool:
        return self._state in CASE_TERMINAL_STATES

    def _require_human(self, actor: Actor, action: str) -> None:
        if not actor.is_human:
            raise UnauthorizedDomainAction(
                f"only a human actor may {action} an InvestigationCase"
            )

    def _transition(self, target: CaseState, *, reason: str) -> None:
        edge = (self._state, target)
        if edge not in LEGAL_CASE_TRANSITIONS:
            raise InvalidStateTransition(self._state, target, reason)

    def start_review(self, *, actor: Actor) -> None:
        self._require_human(actor, "start_review")
        self._transition(
            CaseState.UNDER_REVIEW,
            reason="start_review only from OPEN",
        )
        self._state = CaseState.UNDER_REVIEW

    def _attach_decision(self, decision: HumanDecision) -> None:
        if decision is None:
            raise DomainValidationError(
                "case conclusions require a HumanDecision"
            )
        if decision.case_id != self._case_id:
            raise DomainValidationError(
                "HumanDecision.case_id must match InvestigationCase.case_id"
            )
        self._decision_ids.append(decision.decision_id)

    def close(self, *, actor: Actor, decision: HumanDecision) -> None:
        self._require_human(actor, "close")
        if decision is None:
            raise DomainValidationError(
                "case conclusions require a HumanDecision"
            )
        self._transition(
            CaseState.CLOSED,
            reason="close only from UNDER_REVIEW",
        )
        self._attach_decision(decision)
        self._state = CaseState.CLOSED

    def dismiss(self, *, actor: Actor, decision: HumanDecision) -> None:
        self._require_human(actor, "dismiss")
        if decision is None:
            raise DomainValidationError(
                "case conclusions require a HumanDecision"
            )
        self._transition(
            CaseState.DISMISSED,
            reason="dismiss only from OPEN or UNDER_REVIEW",
        )
        self._attach_decision(decision)
        self._state = CaseState.DISMISSED

    def record_review_decision(self, *, actor: Actor, decision: HumanDecision) -> None:
        """Attach a non-concluding HumanDecision; OPEN moves to UNDER_REVIEW."""
        self._require_human(actor, "record a decision on")
        if self.is_terminal:
            raise InvalidStateTransition(
                self._state,
                self._state,
                "cannot record decisions on a terminal case",
            )
        if self._state is CaseState.OPEN:
            self.start_review(actor=actor)
        self._attach_decision(decision)

    def attach_signals(self, signal_ids: tuple[str, ...] | list[str]) -> None:
        if self.is_terminal:
            raise InvalidStateTransition(
                self._state,
                self._state,
                "cannot attach signals to a terminal case",
            )
        extra = tuple(sid for sid in signal_ids if sid not in self._signal_ids)
        self._signal_ids = self._signal_ids + extra
