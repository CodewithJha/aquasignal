"""PostgreSQL connection presented through the sqlite3 DB-API surface.

The repositories are written against ``sqlite3`` (``?`` placeholders,
``sqlite3.Row``-style access, ``sqlite3.Error`` handling, ``lastrowid``).
``PostgresConnection`` wraps a psycopg connection so those repositories run
unchanged on PostgreSQL:

- ``?`` placeholders become ``%s``; literal ``%`` is escaped.
- Rows support both ``row[0]`` and ``row["column"]``.
- psycopg errors are re-raised as ``sqlite3.IntegrityError`` /
  ``sqlite3.OperationalError`` so existing ``except sqlite3.Error`` paths hold.
- ``BEGIN IMMEDIATE`` becomes ``BEGIN`` plus a transaction-scoped advisory
  lock: like SQLite's single writer, every UnitOfWork is serialized, so
  read-then-write (revision / expected_version) checks cannot interleave.
- ``lock_timeout`` mirrors SQLite's ``busy_timeout``.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator, Sequence
from typing import Any

import psycopg
from psycopg import pq

# Arbitrary constant shared by every process using this database.
_UOW_ADVISORY_LOCK_KEY = 0x41515347  # "AQSG"


class Row:
    """Index- and name-addressable row, like ``sqlite3.Row``."""

    __slots__ = ("_values", "_index")

    def __init__(self, values: Sequence[Any], index: dict[str, int]) -> None:
        self._values = tuple(values)
        self._index = index

    def __getitem__(self, key: int | str) -> Any:
        if isinstance(key, str):
            return self._values[self._index[key]]
        return self._values[key]

    def keys(self) -> list[str]:
        return list(self._index)

    def __iter__(self) -> Iterator[Any]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Row):
            return self._values == other._values and self._index == other._index
        return NotImplemented

    __hash__ = None  # type: ignore[assignment]

    def __repr__(self) -> str:
        return f"Row({dict(zip(self._index, self._values, strict=True))!r})"


def _row_factory(cursor: psycopg.Cursor[Any]):
    description = cursor.description or []
    index = {col.name: i for i, col in enumerate(description)}
    return lambda values: Row(values, index)


def translate_placeholders(sql: str) -> str:
    """``?`` → ``%s`` outside quoted literals; escape ``%`` for psycopg."""
    out: list[str] = []
    quote: str | None = None
    for ch in sql:
        if ch == "%":
            out.append("%%")
            continue
        if quote:
            if ch == quote:
                quote = None
            out.append(ch)
            continue
        if ch in ("'", '"'):
            quote = ch
            out.append(ch)
        elif ch == "?":
            out.append("%s")
        else:
            out.append(ch)
    return "".join(out)


def _adapt_params(params: Sequence[Any]) -> tuple[Any, ...]:
    # SQLite stores bools as 0/1 in INTEGER columns; PostgreSQL would reject them.
    return tuple(int(p) if isinstance(p, bool) else p for p in params)


def _translate_error(exc: psycopg.Error) -> sqlite3.Error:
    if isinstance(exc, psycopg.errors.IntegrityError):
        return sqlite3.IntegrityError(str(exc))
    return sqlite3.OperationalError(str(exc))


class PostgresCursor:
    def __init__(self, conn: PostgresConnection, cursor: psycopg.Cursor[Any]) -> None:
        self._conn = conn
        self._cursor = cursor

    @property
    def rowcount(self) -> int:
        return self._cursor.rowcount

    @property
    def lastrowid(self) -> int:
        """Last identity value generated in this session (``lastval()``)."""
        return int(self._conn.execute("SELECT lastval()").fetchone()[0])

    def fetchone(self) -> Row | None:
        try:
            return self._cursor.fetchone() if self._cursor.description else None
        except psycopg.Error as exc:
            raise _translate_error(exc) from exc

    def fetchall(self) -> list[Row]:
        try:
            return self._cursor.fetchall() if self._cursor.description else []
        except psycopg.Error as exc:
            raise _translate_error(exc) from exc

    def __iter__(self) -> Iterator[Row]:
        return iter(self.fetchall())


class PostgresConnection:
    dialect = "postgresql"

    def __init__(self, raw: psycopg.Connection[Any]) -> None:
        self._raw = raw

    def execute(self, sql: str, params: Sequence[Any] = ()) -> PostgresCursor:
        statement = sql.strip().rstrip(";").strip()
        if statement.upper() == "BEGIN IMMEDIATE":
            self._run("BEGIN")
            return self._run("SELECT pg_advisory_xact_lock(%s)", (_UOW_ADVISORY_LOCK_KEY,))
        if params:
            return self._run(translate_placeholders(sql), _adapt_params(params))
        return self._run(sql)

    def executescript(self, sql: str) -> None:
        self._run(sql)

    def _run(self, sql: str, params: Sequence[Any] | None = None) -> PostgresCursor:
        cursor = self._raw.cursor(row_factory=_row_factory)
        try:
            cursor.execute(sql, params)
        except psycopg.Error as exc:
            raise _translate_error(exc) from exc
        return PostgresCursor(self, cursor)

    def _in_transaction(self) -> bool:
        return self._raw.info.transaction_status != pq.TransactionStatus.IDLE

    def commit(self) -> None:
        if self._in_transaction():
            self._run("COMMIT")

    def rollback(self) -> None:
        if self._in_transaction():
            self._run("ROLLBACK")

    def close(self) -> None:
        self._raw.close()


def connect_postgres(url: str, *, lock_timeout_ms: int) -> PostgresConnection:
    """Open an autocommit connection; transactions are explicit (``BEGIN``)."""
    try:
        raw = psycopg.connect(url, autocommit=True, connect_timeout=10)
    except psycopg.Error as exc:
        raise _translate_error(exc) from exc
    conn = PostgresConnection(raw)
    try:
        conn.execute(f"SET lock_timeout = {int(lock_timeout_ms)}")
    except sqlite3.Error:
        conn.close()
        raise
    return conn
