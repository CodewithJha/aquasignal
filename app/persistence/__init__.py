"""SQLite persistence for ConfirmGate Phase 4 + AquaSignal Phase A2.

Implements application ports. Domain stays free of sqlite3.
"""

from app.persistence.config import DatabaseSettings, resolve_sqlite_path
from app.persistence.factory import open_unit_of_work, prepare_database
from app.persistence.duplicate_lookup import SqliteDuplicateLookup

__all__ = [
    "DatabaseSettings",
    "resolve_sqlite_path",
    "open_unit_of_work",
    "prepare_database",
    "SqliteDuplicateLookup",
]
