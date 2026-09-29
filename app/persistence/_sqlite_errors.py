"""Shared SQLite integrity → application error translation for AquaSignal repos."""

from __future__ import annotations

import sqlite3

from app.application.errors import ForeignKeyViolation, PersistenceFailure


def raise_integrity(exc: sqlite3.IntegrityError, *, context: str) -> None:
    msg = str(exc).lower()
    if "foreign key" in msg:
        raise ForeignKeyViolation(f"foreign key constraint failed ({context})") from exc
    raise PersistenceFailure(f"integrity constraint failed ({context})") from exc
