"""Open database connections, run migrations, build UnitOfWork factories.

SQLite (``sqlite:///…`` / path) is the default; ``postgres://`` /
``postgresql://`` DATABASE_URLs use ``app.persistence.postgres``.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from pathlib import Path

from app.application.errors import PersistenceFailure
from app.persistence.config import DatabaseSettings
from app.persistence.migrations_runner import apply_migrations
from app.persistence.unit_of_work import SqliteUnitOfWork

# Writers wait this long for the lock instead of failing with "database is locked".
BUSY_TIMEOUT_MS = 5000


def connect(target: Path | DatabaseSettings) -> sqlite3.Connection:
    """Open a connection to a SQLite path or to the configured database."""
    if isinstance(target, DatabaseSettings):
        if target.postgres_url:
            return _connect_postgres(target.postgres_url)
        target = target.sqlite_path
    sqlite_path = target
    try:
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(
            str(sqlite_path),
            isolation_level=None,  # manual BEGIN via UnitOfWork
            # Each connection is owned by one UnitOfWork; FastAPI may run the
            # request (and so the UoW) on a different worker thread than the
            # one that opened it, but never concurrently.
            check_same_thread=False,
            timeout=BUSY_TIMEOUT_MS / 1000,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
        return conn
    except sqlite3.Error as exc:
        raise PersistenceFailure("failed to open database") from exc


def _connect_postgres(url: str):
    from app.persistence.postgres import connect_postgres

    try:
        return connect_postgres(url, lock_timeout_ms=BUSY_TIMEOUT_MS)
    except sqlite3.Error as exc:
        raise PersistenceFailure("failed to open database") from exc


def database_reachable(target: Path | DatabaseSettings) -> bool:
    """Liveness probe: open the DB and run a trivial query. Never raises."""
    try:
        conn = connect(target)
    except (PersistenceFailure, OSError):
        return False
    try:
        conn.execute("SELECT 1").fetchone()
        return True
    except sqlite3.Error:
        return False
    finally:
        conn.close()


def prepare_database(settings: DatabaseSettings) -> sqlite3.Connection:
    """Open the DB (WAL for SQLite), apply pending migrations. Returns a live connection."""
    conn = connect(settings)
    if settings.sqlite_path is not None:
        try:
            conn.execute("PRAGMA journal_mode = WAL")
        except sqlite3.Error as exc:
            conn.close()
            raise PersistenceFailure("failed to enable WAL journal mode") from exc
    try:
        apply_migrations(conn)
    except Exception:
        conn.close()
        raise
    return conn


def open_unit_of_work(
    settings: DatabaseSettings,
) -> tuple[sqlite3.Connection, Callable[[], SqliteUnitOfWork]]:
    """Prepare DB and return (migration_connection, uow_factory).

    Every UnitOfWork from the factory opens and closes its own connection, so
    no connection or transaction is shared across requests or threads. The
    returned connection is only the one used for migrations; callers may use
    it for inspection and must close it.
    """
    conn = prepare_database(settings)

    def factory() -> SqliteUnitOfWork:
        return SqliteUnitOfWork(connect(settings), owns_connection=True)

    return conn, factory
