"""Database configuration — DATABASE_URL or safe default path."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# Default under project data/ — not a shared machine global DB.
_DEFAULT_RELATIVE = Path("data") / "confirmgate.sqlite3"


@dataclass(frozen=True, slots=True)
class DatabaseSettings:
    """Resolved SQLite filesystem path (Postgres later via different adapter)."""

    sqlite_path: Path

    @classmethod
    def from_env(cls, *, project_root: Path | None = None) -> DatabaseSettings:
        root = project_root or Path.cwd()
        raw = os.environ.get("DATABASE_URL", "").strip()
        path = resolve_sqlite_path(raw, project_root=root)
        return cls(sqlite_path=path)


def resolve_sqlite_path(database_url: str, *, project_root: Path) -> Path:
    """Parse DATABASE_URL into a filesystem path.

    Supported:
      - empty → {project_root}/data/confirmgate.sqlite3
      - sqlite:///relative/or/absolute.db
      - sqlite:////absolute/path.db
      - bare filesystem path
    """
    if not database_url:
        return (project_root / _DEFAULT_RELATIVE).resolve()

    url = database_url.strip()
    if url.startswith("sqlite:////"):
        # sqlite:////abs → /abs
        return Path("/" + url[len("sqlite:////") :]).resolve()
    if url.startswith("sqlite:///"):
        rest = url[len("sqlite:///") :]
        path = Path(rest)
        if not path.is_absolute():
            path = project_root / path
        return path.resolve()
    if url.startswith("sqlite://"):
        # sqlite://localhost/path or sqlite:/// — treat remainder as path-ish
        rest = url[len("sqlite://") :]
        if rest.startswith("/"):
            return Path(rest).resolve()
        return (project_root / rest).resolve()

    path = Path(url)
    if not path.is_absolute():
        path = project_root / path
    return path.resolve()
