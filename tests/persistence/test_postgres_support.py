"""PostgreSQL support that needs no server: URL parsing, SQL translation, migration parity."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.persistence.config import DatabaseSettings
from app.persistence.migrations_runner import list_migration_files
from app.persistence.postgres import Row, translate_placeholders


@pytest.mark.parametrize(
    "url", ["postgres://u:p@host/db", "postgresql://u:p@host:5432/db?sslmode=require"]
)
def test_postgres_url_selects_postgres(monkeypatch: pytest.MonkeyPatch, url: str) -> None:
    monkeypatch.setenv("DATABASE_URL", url)
    settings = DatabaseSettings.from_env(project_root=Path("/tmp"))
    assert settings.dialect == "postgresql"
    assert settings.postgres_url == url
    assert settings.sqlite_path is None


def test_sqlite_url_keeps_sqlite(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite:///data/x.sqlite3")
    settings = DatabaseSettings.from_env(project_root=tmp_path)
    assert settings.dialect == "sqlite"
    assert settings.sqlite_path == (tmp_path / "data" / "x.sqlite3").resolve()
    assert settings.postgres_url is None


def test_settings_require_exactly_one_target(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        DatabaseSettings()
    with pytest.raises(ValueError):
        DatabaseSettings(sqlite_path=tmp_path / "a.db", postgres_url="postgresql://h/db")


def test_placeholders_translated_outside_literals() -> None:
    sql = "SELECT * FROM t WHERE a = ? AND b = '?' AND c LIKE 'x%' AND d IN (?, ?)"
    assert translate_placeholders(sql) == (
        "SELECT * FROM t WHERE a = %s AND b = '?' AND c LIKE 'x%%' AND d IN (%s, %s)"
    )


def test_row_supports_index_and_name_access() -> None:
    row = Row(("r1", 3), {"run_id": 0, "n": 1})
    assert row[0] == "r1" and row["n"] == 3
    assert tuple(row) == ("r1", 3)
    assert dict(zip(row.keys(), row, strict=True)) == {"run_id": "r1", "n": 3}


def test_postgres_migrations_mirror_sqlite_versions() -> None:
    sqlite = [(v, p.name) for v, p in list_migration_files("sqlite")]
    postgres = [(v, p.name) for v, p in list_migration_files("postgresql")]
    assert sqlite == postgres
    assert [v for v, _ in sqlite] == [1, 2, 3, 4, 5]
