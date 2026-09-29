"""Ordered, reviewable schema migrations (no Alembic)."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.application.errors import MigrationFailure

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
# Same versions and semantics as MIGRATIONS_DIR, in PostgreSQL syntax.
POSTGRES_MIGRATIONS_DIR = MIGRATIONS_DIR / "postgres"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dialect(conn: sqlite3.Connection) -> str:
    return getattr(conn, "dialect", "sqlite")


def list_migration_files(dialect: str = "sqlite") -> list[tuple[int, Path]]:
    directory = POSTGRES_MIGRATIONS_DIR if dialect == "postgresql" else MIGRATIONS_DIR
    files: list[tuple[int, Path]] = []
    if not directory.is_dir():
        return files
    for path in sorted(directory.glob("*.sql")):
        stem = path.stem  # e.g. 001_initial
        try:
            version = int(stem.split("_", 1)[0])
        except ValueError as exc:
            raise MigrationFailure(f"invalid migration filename: {path.name}") from exc
        files.append((version, path))
    files.sort(key=lambda item: item[0])
    return files


def applied_versions(conn: sqlite3.Connection) -> set[int]:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY NOT NULL,
            applied_at TEXT NOT NULL,
            name TEXT NOT NULL
        )
        """
    )
    rows = conn.execute("SELECT version FROM schema_migrations").fetchall()
    return {int(r[0]) for r in rows}


def apply_migrations(conn: sqlite3.Connection) -> list[int]:
    """Apply pending migrations in version order. Returns newly applied versions."""
    dialect = _dialect(conn)
    try:
        if dialect == "postgresql":
            # Transactional DDL under the UoW lock: concurrent starters (e.g. a
            # zero-downtime deploy overlap) apply each migration exactly once.
            conn.execute("BEGIN IMMEDIATE")
        applied = applied_versions(conn)
        newly: list[int] = []
        for version, path in list_migration_files(dialect):
            if version in applied:
                continue
            sql = path.read_text(encoding="utf-8")
            try:
                conn.executescript(sql)
                conn.execute(
                    "INSERT INTO schema_migrations (version, applied_at, name) VALUES (?, ?, ?)",
                    (version, _utc_now_iso(), path.name),
                )
                newly.append(version)
            except sqlite3.Error as exc:
                raise MigrationFailure(
                    f"failed applying migration {path.name}: {exc}"
                ) from exc
        conn.commit()
        return newly
    except MigrationFailure:
        conn.rollback()
        raise
    except sqlite3.Error as exc:
        conn.rollback()
        raise MigrationFailure(f"migration bookkeeping failed: {exc}") from exc
