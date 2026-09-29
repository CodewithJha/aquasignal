"""P4.1 — opening a case is idempotent per AnalysisRun (double-click safe)."""

from __future__ import annotations

import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.composition import build_services, reset_services, set_services
from app.demo.fixture_loader import load_fixture
from app.domain.investigation.enums import DecisionCode
from app.flags.engine import DeterministicFlagEngine
from app.main import app
from app.persistence.factory import open_unit_of_work
from app.persistence.migrations_runner import apply_migrations, list_migration_files
from tests.db import make_settings
from tests.application.aquasignal.conftest import make_analysis_params

WORKERS = 8


@pytest.fixture
def run_id(analysis, coimbra, analysis_window, baseline_window, recent_window) -> str:
    params = make_analysis_params(coimbra, analysis_window, baseline_window, recent_window)
    outcome = analysis.analyze(
        site=coimbra,
        time_window=analysis_window,
        fixture_observations=load_fixture("A_temporal_shift"),
        params=params,
    )
    return outcome.run.run_id


def _case_ids_for_run(uow_factory, run_id: str) -> list[str]:
    with uow_factory() as uow:
        rows = uow._conn.execute(  # noqa: SLF001
            "SELECT case_id FROM investigation_cases WHERE analysis_run_id = ?",
            (run_id,),
        ).fetchall()
    return [r[0] for r in rows]


def test_sequential_double_open_returns_same_case(investigation, uow_factory, run_id, reviewer) -> None:
    first = investigation.open_case_for_run(analysis_run_id=run_id, opened_by=reviewer)
    second = investigation.open_case_for_run(analysis_run_id=run_id, opened_by=reviewer)
    assert second.case.case_id == first.case.case_id
    assert _case_ids_for_run(uow_factory, run_id) == [first.case.case_id]


def test_parallel_open_creates_one_case(investigation, uow_factory, run_id, reviewer) -> None:
    barrier = threading.Barrier(WORKERS)

    def open_once(_: int) -> str:
        barrier.wait()
        return investigation.open_case_for_run(
            analysis_run_id=run_id, opened_by=reviewer
        ).case.case_id

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        ids = list(pool.map(open_once, range(WORKERS)))

    assert len(set(ids)) == 1
    assert _case_ids_for_run(uow_factory, run_id) == [ids[0]]


def test_new_case_allowed_after_previous_is_terminal(investigation, run_id, reviewer) -> None:
    first = investigation.open_case_for_run(analysis_run_id=run_id, opened_by=reviewer)
    investigation.record_decision(
        case_id=first.case.case_id,
        actor=reviewer,
        decision_code=DecisionCode.DISMISS,
        rationale="Not actionable.",
        expected_version=first.version,
    )
    second = investigation.open_case_for_run(analysis_run_id=run_id, opened_by=reviewer)
    assert second.case.case_id != first.case.case_id


def test_db_trigger_refuses_second_active_case(uow_factory, run_id) -> None:
    with uow_factory() as uow:
        conn = uow._conn  # noqa: SLF001
        row = dict(
            conn.execute("SELECT * FROM analysis_runs WHERE run_id = ?", (run_id,)).fetchone()
        )
    insert = """
        INSERT INTO investigation_cases (
            case_id, site_id, city, display_name, window_start, window_end,
            analysis_run_id, reproducibility_ref, opened_at, state, version
        ) VALUES (?, 'coimbra', 'Coimbra', 'Coimbra', ?, ?, ?, 'ref', ?, ?, 1)
    """
    args = (row["window_start"], row["window_end"], run_id, "2026-09-27T00:00:00+00:00")
    # Separate transactions: PostgreSQL aborts a transaction after any error.
    with uow_factory() as uow:
        uow._conn.execute(insert, ("case_raw_1", *args, "OPEN"))  # noqa: SLF001
        uow.commit()
    with uow_factory() as uow:
        with pytest.raises(
            sqlite3.IntegrityError, match="one active investigation case|one_active_per_run"
        ):
            uow._conn.execute(insert, ("case_raw_2", *args, "UNDER_REVIEW"))  # noqa: SLF001
    with uow_factory() as uow:
        uow._conn.execute(insert, ("case_raw_3", *args, "CLOSED"))  # noqa: SLF001


def test_migration_applies_to_pre_existing_db_with_duplicates(tmp_path: Path) -> None:
    """Old DBs may already hold duplicate active cases; migration must not fail or delete them."""
    conn = sqlite3.connect(tmp_path / "legacy.sqlite3")
    conn.execute(
        "CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY NOT NULL,"
        " applied_at TEXT NOT NULL, name TEXT NOT NULL)"
    )
    for version, path in list_migration_files():
        if version >= 4:
            continue
        conn.executescript(path.read_text(encoding="utf-8"))
        conn.execute(
            "INSERT INTO schema_migrations VALUES (?, 'legacy', ?)", (version, path.name)
        )
    for cid in ("case_dup_1", "case_dup_2"):
        conn.execute(
            """
            INSERT INTO investigation_cases (
                case_id, site_id, city, display_name, window_start, window_end,
                analysis_run_id, reproducibility_ref, opened_at, state, version
            ) VALUES (?, 'coimbra', 'Coimbra', 'Coimbra', 'a', 'b', 'run_legacy',
                      'ref', '2026-09-20', 'OPEN', 1)
            """,
            (cid,),
        )
    conn.commit()

    assert apply_migrations(conn) == [4, 5]
    ids = [r[0] for r in conn.execute("SELECT case_id FROM investigation_cases ORDER BY case_id")]
    assert ids == ["case_dup_1", "case_dup_2"]
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO investigation_cases (
                case_id, site_id, city, display_name, window_start, window_end,
                analysis_run_id, reproducibility_ref, opened_at, state, version
            ) VALUES ('case_dup_3', 'coimbra', 'Coimbra', 'Coimbra', 'a', 'b',
                      'run_legacy', 'ref', '2026-09-21', 'OPEN', 1)
            """
        )
    conn.close()


def test_http_double_post_open_case_one_case(
    tmp_path: Path, coimbra, analysis_window, baseline_window, recent_window
) -> None:
    settings = make_settings(tmp_path / "http.sqlite3")
    services = build_services(settings=settings, flag_engine=DeterministicFlagEngine())
    run = services.analysis.analyze(
        site=coimbra,
        time_window=analysis_window,
        fixture_observations=load_fixture("A_temporal_shift"),
        params=make_analysis_params(coimbra, analysis_window, baseline_window, recent_window),
    ).run
    reset_services()
    set_services(services)
    try:
        with TestClient(app) as client:
            url = f"/investigate/analyses/{run.run_id}/cases"
            r1 = client.post(url, follow_redirects=False)
            r2 = client.post(url, follow_redirects=False)
            assert r1.status_code == r2.status_code == 303
            assert r2.headers["location"] == f"/investigate/analyses/{run.run_id}"
        _conn, factory = open_unit_of_work(settings)
        _conn.close()
        assert len(_case_ids_for_run(factory, run.run_id)) == 1
    finally:
        reset_services()
