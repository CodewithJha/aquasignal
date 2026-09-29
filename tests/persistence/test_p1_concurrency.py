"""P1.1 — per-UnitOfWork SQLite connections under concurrent threads."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.application.errors import ConcurrencyConflict
from app.composition import build_services, reset_services, set_services
from app.demo.fixture_loader import load_fixture
from app.domain.enums import ActorType
from app.domain.investigation.enums import DecisionCode
from app.domain.signal.value_objects import TimeWindow
from app.domain.sites import get_site
from app.domain.value_objects import Actor, FieldValue
from app.flags.engine import DeterministicFlagEngine
from app.main import app
from app.persistence.factory import open_unit_of_work
from tests.db import make_settings, sqlite_only
from tests.application.aquasignal.conftest import make_analysis_params

WORKERS = 8


@pytest.fixture
def services(tmp_path: Path):
    svc = build_services(
        settings=make_settings(tmp_path / "concurrency.sqlite3"),
        flag_engine=DeterministicFlagEngine(),
    )
    yield svc


def test_uow_connections_are_not_shared(tmp_path: Path) -> None:
    conn, factory = open_unit_of_work(make_settings(tmp_path / "iso.sqlite3"))
    conn.close()
    a, b = factory(), factory()
    assert a._conn is not b._conn  # noqa: SLF001
    with a:
        pass
    with pytest.raises(Exception):
        a._conn.execute("SELECT 1")  # noqa: SLF001 — closed on exit


@sqlite_only
def test_wal_and_busy_timeout_enabled(tmp_path: Path) -> None:
    conn, factory = open_unit_of_work(make_settings(tmp_path / "wal.sqlite3"))
    assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    conn.close()
    uow = factory()
    assert uow._conn.execute("PRAGMA busy_timeout").fetchone()[0] >= 1000  # noqa: SLF001
    uow._conn.close()  # noqa: SLF001


def test_concurrent_submits_all_persist(services) -> None:
    coimbra = get_site("coimbra")
    barrier = threading.Barrier(WORKERS)

    def submit(i: int) -> str:
        barrier.wait()
        record = services.flow.submit(
            site=coimbra,
            fields={
                "foam": FieldValue(code="foam", value="present"),
                "colour": FieldValue(code="colour", value="clear"),
                "smell": FieldValue(code="smell", value="none"),
            },
            notes=f"thread {i}",
        )
        return record.packet.packet_id

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        ids = list(pool.map(submit, range(WORKERS)))

    assert len(set(ids)) == WORKERS
    for pid in ids:
        assert services.flow.get(pid).packet.notes is not None


def test_concurrent_decisions_one_winner(services) -> None:
    coimbra = get_site("coimbra")
    window = TimeWindow(
        start=datetime(2026, 6, 1, tzinfo=timezone.utc),
        end=datetime(2026, 9, 30, tzinfo=timezone.utc),
    )
    params = make_analysis_params(
        coimbra,
        window,
        TimeWindow(start=window.start, end=datetime(2026, 8, 1, tzinfo=timezone.utc)),
        TimeWindow(start=datetime(2026, 9, 1, tzinfo=timezone.utc), end=window.end),
    )
    outcome = services.analysis.analyze(
        site=coimbra,
        time_window=window,
        fixture_observations=load_fixture("A_temporal_shift"),
        params=params,
    )
    reviewer = Actor(ActorType.REVIEWER, "reviewer-conc")
    record = services.investigation.open_case_for_run(
        analysis_run_id=outcome.run.run_id, opened_by=reviewer
    )
    barrier = threading.Barrier(WORKERS)

    def decide(i: int) -> str:
        barrier.wait()
        try:
            services.investigation.record_decision(
                case_id=record.case.case_id,
                actor=reviewer,
                decision_code=DecisionCode.NOTE,
                rationale=f"note {i}",
                expected_version=record.version,
            )
            return "ok"
        except ConcurrencyConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        results = list(pool.map(decide, range(WORKERS)))

    assert results.count("ok") == 1
    assert results.count("conflict") == WORKERS - 1
    assert len(services.investigation.list_decisions(record.case.case_id)) == 1


def test_concurrent_http_requests(services) -> None:
    reset_services()
    set_services(services)
    try:
        with TestClient(app) as client:

            def upload(i: int) -> int:
                r = client.post(
                    "/upload",
                    data={"site": "ghent", "foam": "present", "colour": "clear", "smell": "none"},
                    follow_redirects=False,
                )
                return r.status_code

            def read(_: int) -> int:
                return client.get("/investigate/sites/ghent").status_code

            with ThreadPoolExecutor(max_workers=WORKERS) as pool:
                writes = [pool.submit(upload, i) for i in range(WORKERS)]
                reads = [pool.submit(read, i) for i in range(WORKERS)]
                assert all(f.result() == 303 for f in writes)
                assert all(f.result() == 200 for f in reads)
    finally:
        reset_services()
