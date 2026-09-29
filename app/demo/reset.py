"""Restore the configured database to the seeded public-demo state.

Usage (from repo root or inside the container):

    DEMO_MODE=true python -m app.demo.reset

Takes no arguments: it only ever targets ``DATABASE_URL``. Refuses to run
unless ``DEMO_MODE`` is enabled.

Strategy: apply pending migrations, delete every data row in one
``BEGIN IMMEDIATE`` transaction (``schema_migrations`` is kept), then re-run
``app.demo.seed``. The file is never replaced, so a server holding WAL
connections stays consistent; requests during the few-millisecond gap between
wipe and re-seed may briefly see an empty dataset.
"""

from __future__ import annotations

import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

from app.ai.config import AiSettings
from app.composition import REPO_ROOT, build_services
from app.demo.config import DemoSettings
from app.demo.seed import seed_coimbra_demo
from app.persistence.config import DatabaseSettings
from app.persistence.factory import connect, prepare_database

_KEEP_TABLES = frozenset({"schema_migrations"})


class DemoResetRefused(RuntimeError):
    """Raised when a reset is requested without DEMO_MODE enabled."""


@dataclass(frozen=True, slots=True)
class DemoResetResult:
    run_ids: tuple[str, ...]
    evidence_items: int
    analysis_runs: int
    investigation_cases: int
    observation_packets: int


def _data_tables(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return sorted(r[0] for r in rows if r[0] not in _KEEP_TABLES)


def _clear_data(conn: sqlite3.Connection) -> None:
    # Must be set outside a transaction; every table is emptied, so no
    # dangling references remain at commit.
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("BEGIN IMMEDIATE")
    try:
        for table in _data_tables(conn):
            conn.execute(f'DELETE FROM "{table}"')
        has_sequence = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'sqlite_sequence'"
        ).fetchone()
        if has_sequence:
            conn.execute("DELETE FROM sqlite_sequence")
        conn.execute("COMMIT")
    except sqlite3.Error:
        conn.execute("ROLLBACK")
        raise


def _count(sqlite_path: Path, table: str) -> int:
    conn = connect(sqlite_path)
    try:
        return int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
    finally:
        conn.close()


def reset_demo_database(
    *,
    settings: DatabaseSettings | None = None,
    demo: DemoSettings | None = None,
) -> DemoResetResult:
    """Wipe data rows and re-seed synthetic fixtures. Requires DEMO_MODE."""
    demo = demo or DemoSettings.from_env()
    if not demo.demo_mode:
        raise DemoResetRefused("DEMO_MODE is not enabled")
    resolved = settings or DatabaseSettings.from_env(project_root=REPO_ROOT)

    conn = prepare_database(resolved)
    try:
        _clear_data(conn)
    finally:
        conn.close()

    services = build_services(settings=resolved, ai_settings=AiSettings())
    run_ids = seed_coimbra_demo(services.analysis, services.investigation)
    path = resolved.sqlite_path
    return DemoResetResult(
        run_ids=tuple(run_ids),
        evidence_items=_count(path, "evidence_items"),
        analysis_runs=_count(path, "analysis_runs"),
        investigation_cases=_count(path, "investigation_cases"),
        observation_packets=_count(path, "observation_packets"),
    )


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args:
        print(
            "usage: DEMO_MODE=true python -m app.demo.reset  (no arguments; "
            "resets the database configured by DATABASE_URL)",
            file=sys.stderr,
        )
        return 2
    try:
        result = reset_demo_database()
    except DemoResetRefused:
        print("Demo reset refused: DEMO_MODE is not enabled.", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 — report type only, never paths or SQL
        print(f"Demo reset failed ({type(exc).__name__}).", file=sys.stderr)
        return 1
    print(
        "Demo dataset reset: "
        f"{result.analysis_runs} synthetic analysis runs, "
        f"{result.evidence_items} synthetic evidence items, "
        f"{result.investigation_cases} open investigation case(s), "
        f"{result.observation_packets} observations."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
