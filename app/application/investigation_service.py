"""InvestigationService — human-owned case lifecycle (no UI).

Opens an InvestigationCase from a SUCCEEDED AnalysisRun and records
HumanDecisions on it. AI actors are refused by the domain.
"""

from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

from app.application.errors import AnalysisOrchestrationError, DuplicateResource
from app.application.ports import CaseRecord, UnitOfWork
from app.domain.errors import DomainValidationError
from app.domain.investigation.case import InvestigationCase
from app.domain.investigation.decision import HumanDecision
from app.domain.investigation.enums import AnalysisRunStatus, CaseState, DecisionCode
from app.domain.signal.value_objects import TimeWindow
from app.domain.sites import get_site
from app.domain.value_objects import Actor, SiteRef

# Decision codes a reviewer may record on an existing case, by effect.
CONCLUDING_CODES: frozenset[DecisionCode] = frozenset(
    {DecisionCode.CONCLUDE_INSUFFICIENT, DecisionCode.CONCLUDE_CHANGE_SUSPECTED}
)
REVIEW_CODES: frozenset[DecisionCode] = frozenset(
    {DecisionCode.NOTE, DecisionCode.REQUEST_MORE_EVIDENCE}
)
RECORDABLE_DECISION_CODES: frozenset[DecisionCode] = (
    CONCLUDING_CODES | REVIEW_CODES | {DecisionCode.DISMISS}
)


def parse_decision_code(raw: str) -> DecisionCode:
    try:
        code = DecisionCode((raw or "").strip())
    except ValueError:
        code = None
    if code is None or code not in RECORDABLE_DECISION_CODES:
        allowed = sorted(c.value for c in RECORDABLE_DECISION_CODES)
        raise DomainValidationError(
            f"decision_code must be one of {allowed}; got {raw!r}"
        )
    return code


class InvestigationService:
    """Thin coordinator for InvestigationCase open + HumanDecision record."""

    def __init__(self, uow_factory: Callable[[], UnitOfWork]) -> None:
        self._uow_factory = uow_factory

    def open_case(
        self,
        *,
        site: SiteRef,
        window: TimeWindow,
        analysis_run_id: str,
        opened_by: Actor,
        signal_ids: tuple[str, ...] | None = None,
        case_id: str | None = None,
    ) -> CaseRecord:
        """Open OPEN case linked to a SUCCEEDED run. Human actor required (domain).

        Idempotent per run: if the run already has an OPEN / UNDER_REVIEW case,
        that case is returned instead of creating a second one (double-submit).
        """
        try:
            return self._open_case_once(
                site=site,
                window=window,
                analysis_run_id=analysis_run_id,
                opened_by=opened_by,
                signal_ids=signal_ids,
                case_id=case_id,
            )
        except DuplicateResource:
            with self._uow_factory() as uow:
                existing = uow.investigation_cases.find_active_for_run(analysis_run_id)
            if existing is None:
                raise
            return existing

    def _open_case_once(
        self,
        *,
        site: SiteRef,
        window: TimeWindow,
        analysis_run_id: str,
        opened_by: Actor,
        signal_ids: tuple[str, ...] | None,
        case_id: str | None,
    ) -> CaseRecord:
        with self._uow_factory() as uow:
            run = uow.analysis_runs.require(analysis_run_id)
            if run.status is not AnalysisRunStatus.SUCCEEDED:
                raise AnalysisOrchestrationError(
                    f"cannot open case for run {analysis_run_id} "
                    f"in status {run.status.value}"
                )
            ids = signal_ids
            if ids is None:
                ids = tuple(s.signal_id for s in uow.environmental_signals.list_for_run(run.run_id))
            reproducibility_ref = (
                f"{run.run_id}@{run.snapshot_hash[:16]}:{run.parameters_hash[:16]}"
            )
            case = InvestigationCase.open(
                case_id=case_id or f"case_{uuid4().hex[:12]}",
                site=site,
                window=window,
                analysis_run_id=run.run_id,
                signal_ids=ids,
                reproducibility_ref=reproducibility_ref,
                opened_by=opened_by,
            )
            # After InvestigationCase.open so the human-actor rule still applies.
            existing = uow.investigation_cases.find_active_for_run(run.run_id)
            if existing is not None:
                return existing
            saved = uow.investigation_cases.save(case, expected_version=0)
            uow.commit()
            return saved

    def open_case_for_run(self, *, analysis_run_id: str, opened_by: Actor) -> CaseRecord:
        """Open a case scoped to the run's own site and window."""
        with self._uow_factory() as uow:
            run = uow.analysis_runs.require(analysis_run_id)
        return self.open_case(
            site=get_site(run.site_id),
            window=run.time_window,
            analysis_run_id=run.run_id,
            opened_by=opened_by,
        )

    def record_decision(
        self,
        *,
        case_id: str,
        actor: Actor,
        decision_code: DecisionCode,
        rationale: str,
        expected_version: int,
    ) -> tuple[CaseRecord, HumanDecision]:
        """Persist a HumanDecision and apply its effect on the case atomically.

        ``expected_version`` guards against double-submits and concurrent
        reviewers (ConcurrencyConflict). Terminal cases refuse new decisions.
        """
        if decision_code not in RECORDABLE_DECISION_CODES:
            raise DomainValidationError(
                f"decision_code {decision_code.value!r} cannot be recorded on a case"
            )
        with self._uow_factory() as uow:
            record = uow.investigation_cases.require(case_id)
            case = record.case
            decision = HumanDecision.create(
                actor=actor,
                decision_code=decision_code,
                rationale=rationale,
                linked_signal_ids=case.signal_ids,
                case_id=case.case_id,
            )
            if decision_code is DecisionCode.DISMISS:
                case.dismiss(actor=actor, decision=decision)
            elif decision_code in CONCLUDING_CODES:
                if case.state is CaseState.OPEN:
                    case.start_review(actor=actor)
                case.close(actor=actor, decision=decision)
            else:
                case.record_review_decision(actor=actor, decision=decision)
            # FK order: decision row before the case_decisions link.
            saved_decision = uow.human_decisions.save(decision)
            saved_case = uow.investigation_cases.save(
                case, expected_version=expected_version
            )
            uow.commit()
            return saved_case, saved_decision

    def get_case(self, case_id: str) -> CaseRecord:
        with self._uow_factory() as uow:
            return uow.investigation_cases.require(case_id)

    def list_decisions(self, case_id: str) -> list[HumanDecision]:
        with self._uow_factory() as uow:
            uow.investigation_cases.require(case_id)
            return uow.human_decisions.list_for_case(case_id)