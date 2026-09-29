"""Persistence-backed DuplicateLookup for FlagEngine (site identity heuristic)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from app.application.errors import PersistenceFailure
from app.domain.packet import ObservationPacket
from app.flags.ports import DuplicateLookup, DuplicateMatch
from app.persistence.config import DatabaseSettings


class SqliteDuplicateLookup:
    """Deterministic duplicate candidates: other packets sharing site_ref_id.

    Uses a short-lived read connection so FlagEngine evaluation never nests
    BEGIN on the process write UnitOfWork connection.
    """

    def __init__(self, target: Path | DatabaseSettings) -> None:
        self._settings = (
            target
            if isinstance(target, DatabaseSettings)
            else DatabaseSettings(sqlite_path=Path(target))
        )

    def _connect(self):
        if self._settings.postgres_url:
            from app.persistence.factory import connect

            return connect(self._settings)
        conn = sqlite3.connect(str(self._settings.sqlite_path))
        conn.row_factory = sqlite3.Row
        return conn

    def find_duplicates(self, packet: ObservationPacket) -> tuple[DuplicateMatch, ...]:
        try:
            conn = self._connect()
            try:
                rows = conn.execute(
                    """
                    SELECT packet_id FROM observation_packets
                    WHERE site_ref_id = ? AND packet_id != ?
                    ORDER BY packet_id
                    """,
                    (packet.site_ref_id, packet.packet_id),
                ).fetchall()
            finally:
                conn.close()
        except (sqlite3.Error, PersistenceFailure) as exc:
            raise PersistenceFailure("duplicate lookup failed") from exc
        return tuple(
            DuplicateMatch(
                other_packet_id=str(row["packet_id"]),
                reason=f"same site_ref_id={packet.site_ref_id}",
            )
            for row in rows
        )


_: type[DuplicateLookup] = SqliteDuplicateLookup
