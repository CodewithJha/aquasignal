"""AnalysisRun lifecycle and immutability after SUCCEEDED."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.domain.errors import DomainValidationError, InvalidStateTransition
from app.domain.investigation.analysis_run import AnalysisRun
from app.domain.investigation.enums import AnalysisRunStatus
from app.domain.signal.value_objects import TimeWindow

WINDOW = TimeWindow(
    start=datetime(2026, 9, 1, tzinfo=timezone.utc),
    end=datetime(2026, 9, 22, tzinfo=timezone.utc),
)


def _start(**kwargs) -> AnalysisRun:
    base = dict(
        snapshot_hash="d" * 64,
        detector_set_version="detectors@0.1.0",
        parameters_hash="e" * 64,
        site_id="coimbra",
        time_window=WINDOW,
    )
    base.update(kwargs)
    return AnalysisRun.start(**base)


def test_started_to_succeeded() -> None:
    run = _start()
    assert run.status is AnalysisRunStatus.STARTED
    assert run.site_id == "coimbra"
    assert run.time_window == WINDOW
    run.succeed(signals_produced=("sig_1", "sig_2"))
    assert run.status is AnalysisRunStatus.SUCCEEDED
    assert run.signals_produced == ("sig_1", "sig_2")
    assert run.finished_at is not None
    assert run.is_immutable is True


def test_started_to_failed() -> None:
    run = _start()
    run.fail(error="n < n_min")
    assert run.status is AnalysisRunStatus.FAILED
    assert run.error == "n < n_min"
    assert run.finished_at is not None


def test_immutable_after_succeeded() -> None:
    run = _start(started_at=datetime(2026, 9, 22, tzinfo=timezone.utc))
    run.succeed(signals_produced=())
    with pytest.raises(InvalidStateTransition):
        run.fail(error="late")
    with pytest.raises(InvalidStateTransition):
        run.succeed(signals_produced=("again",))
    with pytest.raises(DomainValidationError, match="immutable"):
        run.record_signal("sig_x")


def test_illegal_fail_then_succeed() -> None:
    run = _start()
    run.fail(error="boom")
    with pytest.raises(InvalidStateTransition):
        run.succeed(signals_produced=())


def test_requires_hashes_and_site() -> None:
    with pytest.raises(DomainValidationError):
        AnalysisRun.start(
            snapshot_hash="",
            detector_set_version="detectors@0.1.0",
            parameters_hash="e" * 64,
            site_id="coimbra",
            time_window=WINDOW,
        )
    with pytest.raises(DomainValidationError):
        AnalysisRun.start(
            snapshot_hash="d" * 64,
            detector_set_version="detectors@0.1.0",
            parameters_hash="e" * 64,
            site_id="",
            time_window=WINDOW,
        )
