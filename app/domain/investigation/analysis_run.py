"""AnalysisRun — versioned detector suite execution; immutable after SUCCEEDED."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.domain.errors import DomainValidationError, InvalidStateTransition
from app.domain.investigation.enums import AnalysisRunStatus
from app.domain.signal.value_objects import TimeWindow


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


LEGAL_RUN_TRANSITIONS: frozenset[tuple[AnalysisRunStatus, AnalysisRunStatus]] = frozenset(
    {
        (AnalysisRunStatus.STARTED, AnalysisRunStatus.SUCCEEDED),
        (AnalysisRunStatus.STARTED, AnalysisRunStatus.FAILED),
    }
)


class AnalysisRun:
    """One detector-suite execution. Terminal after SUCCEEDED or FAILED.

    Self-describing scope: ``site_id`` + ``time_window`` are recorded at start so
    list/detail do not need to reverse-engineer site from snapshot membership.
    """

    def __init__(
        self,
        *,
        run_id: str,
        started_at: datetime,
        snapshot_hash: str,
        detector_set_version: str,
        parameters_hash: str,
        site_id: str,
        time_window: TimeWindow,
        status: AnalysisRunStatus = AnalysisRunStatus.STARTED,
        finished_at: datetime | None = None,
        signals_produced: tuple[str, ...] = (),
        error: str | None = None,
    ) -> None:
        self._run_id = run_id
        self._started_at = started_at
        self._finished_at = finished_at
        self._status = status
        self._snapshot_hash = snapshot_hash
        self._detector_set_version = detector_set_version
        self._parameters_hash = parameters_hash
        self._site_id = site_id
        self._time_window = time_window
        self._signals_produced = signals_produced
        self._error = error

    @classmethod
    def start(
        cls,
        *,
        snapshot_hash: str,
        detector_set_version: str,
        parameters_hash: str,
        site_id: str,
        time_window: TimeWindow,
        started_at: datetime | None = None,
        run_id: str | None = None,
    ) -> AnalysisRun:
        if not snapshot_hash.strip():
            raise DomainValidationError("snapshot_hash is required")
        if not detector_set_version.strip():
            raise DomainValidationError("detector_set_version is required")
        if not parameters_hash.strip():
            raise DomainValidationError("parameters_hash is required")
        if not site_id.strip():
            raise DomainValidationError("site_id is required")
        return cls(
            run_id=run_id or f"run_{uuid4().hex[:12]}",
            started_at=started_at or _utc_now(),
            snapshot_hash=snapshot_hash.strip(),
            detector_set_version=detector_set_version.strip(),
            parameters_hash=parameters_hash.strip(),
            site_id=site_id.strip(),
            time_window=time_window,
        )

    @property
    def run_id(self) -> str:
        return self._run_id

    @property
    def status(self) -> AnalysisRunStatus:
        return self._status

    @property
    def started_at(self) -> datetime:
        return self._started_at

    @property
    def finished_at(self) -> datetime | None:
        return self._finished_at

    @property
    def snapshot_hash(self) -> str:
        return self._snapshot_hash

    @property
    def detector_set_version(self) -> str:
        return self._detector_set_version

    @property
    def parameters_hash(self) -> str:
        return self._parameters_hash

    @property
    def site_id(self) -> str:
        return self._site_id

    @property
    def time_window(self) -> TimeWindow:
        return self._time_window

    @property
    def signals_produced(self) -> tuple[str, ...]:
        return self._signals_produced

    @property
    def error(self) -> str | None:
        return self._error

    @property
    def is_immutable(self) -> bool:
        return self._status is AnalysisRunStatus.SUCCEEDED

    @property
    def is_terminal(self) -> bool:
        return self._status in {
            AnalysisRunStatus.SUCCEEDED,
            AnalysisRunStatus.FAILED,
        }

    def _transition(self, target: AnalysisRunStatus, *, reason: str) -> None:
        edge = (self._status, target)
        if edge not in LEGAL_RUN_TRANSITIONS:
            raise InvalidStateTransition(self._status, target, reason)

    def succeed(
        self,
        *,
        signals_produced: tuple[str, ...] | list[str] = (),
        finished_at: datetime | None = None,
    ) -> None:
        self._transition(
            AnalysisRunStatus.SUCCEEDED,
            reason="succeed only from STARTED",
        )
        self._status = AnalysisRunStatus.SUCCEEDED
        self._signals_produced = tuple(signals_produced)
        self._finished_at = finished_at or _utc_now()
        self._error = None

    def fail(self, *, error: str, finished_at: datetime | None = None) -> None:
        self._transition(
            AnalysisRunStatus.FAILED,
            reason="fail only from STARTED",
        )
        if not error.strip():
            raise DomainValidationError("error message required on FAILED run")
        self._status = AnalysisRunStatus.FAILED
        self._error = error.strip()
        self._finished_at = finished_at or _utc_now()

    def record_signal(self, signal_id: str) -> None:
        """Append a signal id while STARTED only. SUCCEEDED runs are frozen."""
        if self.is_immutable:
            raise DomainValidationError(
                "AnalysisRun is immutable after SUCCEEDED"
            )
        if self._status is not AnalysisRunStatus.STARTED:
            raise DomainValidationError(
                "signals can only be recorded while STARTED"
            )
        if not signal_id.strip():
            raise DomainValidationError("signal_id is required")
        self._signals_produced = self._signals_produced + (signal_id.strip(),)
