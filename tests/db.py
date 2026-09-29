"""Test database selection.

Default: every test gets its own temp SQLite file. With ``TEST_DATABASE_URL``
set to a PostgreSQL URL, the same tests run against PostgreSQL instead — each
temp path maps to a fresh schema (dropped at session end) — and tests that
inspect the SQLite file itself are skipped.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from urllib.parse import quote

import pytest

from app.persistence.config import DatabaseSettings

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "").strip()
POSTGRES = bool(TEST_DATABASE_URL)

sqlite_only = pytest.mark.skipif(POSTGRES, reason="inspects the SQLite file directly")

_SETTINGS_BY_PATH: dict[Path, DatabaseSettings] = {}
CREATED_SCHEMAS: list[str] = []


def _schema_url(schema: str) -> str:
    sep = "&" if "?" in TEST_DATABASE_URL else "?"
    return f"{TEST_DATABASE_URL}{sep}options={quote(f'-csearch_path={schema}')}"


def make_settings(sqlite_path: Path) -> DatabaseSettings:
    """Settings for ``sqlite_path`` — or its PostgreSQL schema stand-in."""
    if not POSTGRES:
        return DatabaseSettings(sqlite_path=sqlite_path)
    key = Path(sqlite_path)
    if key not in _SETTINGS_BY_PATH:
        import psycopg

        schema = f"t_{uuid.uuid4().hex[:16]}"
        with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as conn:
            conn.execute(f'CREATE SCHEMA "{schema}"')
        CREATED_SCHEMAS.append(schema)
        _SETTINGS_BY_PATH[key] = DatabaseSettings(postgres_url=_schema_url(schema))
    return _SETTINGS_BY_PATH[key]


def drop_created_schemas() -> None:
    if not CREATED_SCHEMAS:
        return
    import psycopg

    with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as conn:
        for schema in CREATED_SCHEMAS:
            conn.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
    CREATED_SCHEMAS.clear()
