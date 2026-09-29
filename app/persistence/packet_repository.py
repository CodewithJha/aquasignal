"""SQLite ObservationPacketRepository — parameterized SQL only."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any, Sequence

from app.application.errors import (
    ConcurrencyConflict,
    DuplicatePacket,
    PacketNotFound,
    PersistenceFailure,
)
from app.application.ports import PacketRecord, ReviewQueueItem
from app.application.serialization import (
    document_to_packet,
    dumps_document,
    loads_document,
    packet_to_document,
)
from app.domain.enums import Severity
from app.domain.packet import ObservationPacket
from app.domain.value_objects import QualityFlag


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_dt(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


_SEVERITY_RANK = {
    Severity.HARD_REJECT.value: 3,
    Severity.SOFT_BLOCK_FINALIZE.value: 2,
    Severity.WARN.value: 1,
}


def _summarize_flags(flags: tuple[QualityFlag, ...] | list[QualityFlag]) -> dict[str, Any]:
    hard = soft = warn = 0
    max_sev: str | None = None
    max_rank = 0
    for flag in flags:
        if flag.is_overridden:
            continue
        sev = flag.severity.value
        if flag.severity == Severity.HARD_REJECT:
            hard += 1
        elif flag.severity == Severity.SOFT_BLOCK_FINALIZE:
            soft += 1
        else:
            warn += 1
        rank = _SEVERITY_RANK.get(sev, 0)
        if rank > max_rank:
            max_rank = rank
            max_sev = sev
    standing = [f for f in flags if not f.is_overridden]
    if standing:
        # Concise triage reason: highest-severity message first.
        primary = max(
            standing,
            key=lambda f: _SEVERITY_RANK.get(f.severity.value, 0),
        )
        reason = primary.message[:160]
    else:
        reason = "Queued for reviewer (no standing flags)"
    return {
        "flag_count": hard + soft + warn,
        "hard_count": hard,
        "soft_count": soft,
        "warn_count": warn,
        "max_severity": max_sev,
        "review_reason": reason,
    }


def _queue_item_from_packet(packet: ObservationPacket, row: sqlite3.Row) -> ReviewQueueItem:
    summary = _summarize_flags(packet.flags)
    return ReviewQueueItem(
        packet_id=packet.packet_id,
        site_ref_id=packet.site_ref_id,
        site_label=packet.site.display_name,
        city=packet.site.city,
        workflow_state=packet.workflow_state.value,
        revision=int(row["revision"]),
        created_at=_parse_dt(row["created_at"]),
        effective_at=packet.effective_at,
        flag_count=summary["flag_count"],
        max_severity=summary["max_severity"],
        review_reason=summary["review_reason"],
        hard_count=summary["hard_count"],
        soft_count=summary["soft_count"],
        warn_count=summary["warn_count"],
    )


class SqlitePacketRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get(self, packet_id: str) -> PacketRecord | None:
        try:
            row = self._conn.execute(
                """
                SELECT document_json, revision, created_at, updated_at, observer_ref
                FROM observation_packets
                WHERE packet_id = ?
                """,
                (packet_id,),
            ).fetchone()
        except sqlite3.Error as exc:
            raise PersistenceFailure("failed to load packet") from exc
        if row is None:
            return None
        doc = loads_document(row["document_json"])
        packet = document_to_packet(doc, observer_ref=row["observer_ref"])
        return PacketRecord(
            packet=packet,
            revision=int(row["revision"]),
            created_at=_parse_dt(row["created_at"]),
            updated_at=_parse_dt(row["updated_at"]),
        )

    def exists(self, packet_id: str) -> bool:
        try:
            row = self._conn.execute(
                "SELECT 1 FROM observation_packets WHERE packet_id = ?",
                (packet_id,),
            ).fetchone()
        except sqlite3.Error as exc:
            raise PersistenceFailure("failed to check packet existence") from exc
        return row is not None

    def save(self, packet: ObservationPacket, *, expected_revision: int) -> PacketRecord:
        doc = packet_to_document(packet)
        document_json = dumps_document(doc)
        site_ref_id = packet.site_ref_id
        city = packet.site.city
        workflow_state = packet.workflow_state.value
        flags_rules_version = packet.rule_engine_version
        now = _utc_now_iso()

        try:
            if expected_revision == 0:
                return self._insert(
                    packet_id=packet.packet_id,
                    site_ref_id=site_ref_id,
                    city=city,
                    workflow_state=workflow_state,
                    document_json=document_json,
                    flags_rules_version=flags_rules_version,
                    now=now,
                    packet=packet,
                )
            return self._update(
                packet_id=packet.packet_id,
                site_ref_id=site_ref_id,
                city=city,
                workflow_state=workflow_state,
                document_json=document_json,
                flags_rules_version=flags_rules_version,
                now=now,
                expected_revision=expected_revision,
                packet=packet,
            )
        except (DuplicatePacket, ConcurrencyConflict, PacketNotFound):
            raise
        except sqlite3.IntegrityError as exc:
            # Unique constraint on insert race
            if expected_revision == 0:
                raise DuplicatePacket(packet.packet_id) from exc
            raise PersistenceFailure("packet integrity constraint failed") from exc
        except sqlite3.Error as exc:
            raise PersistenceFailure("failed to save packet") from exc

    def list_ids_for_site(
        self, site_ref_id: str, *, exclude_packet_id: str | None = None
    ) -> list[str]:
        try:
            if exclude_packet_id:
                rows = self._conn.execute(
                    """
                    SELECT packet_id FROM observation_packets
                    WHERE site_ref_id = ? AND packet_id != ?
                    ORDER BY packet_id
                    """,
                    (site_ref_id, exclude_packet_id),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    """
                    SELECT packet_id FROM observation_packets
                    WHERE site_ref_id = ?
                    ORDER BY packet_id
                    """,
                    (site_ref_id,),
                ).fetchall()
        except sqlite3.Error as exc:
            raise PersistenceFailure("failed to list site packets") from exc
        return [str(r["packet_id"]) for r in rows]

    def list_finalized_ids_for_site(self, site_ref_id: str) -> list[str]:
        try:
            rows = self._conn.execute(
                """
                SELECT packet_id FROM observation_packets
                WHERE site_ref_id = ? AND workflow_state = 'FINALIZED'
                ORDER BY packet_id
                """,
                (site_ref_id,),
            ).fetchall()
        except sqlite3.Error as exc:
            raise PersistenceFailure("failed to list finalized site packets") from exc
        return [str(r["packet_id"]) for r in rows]

    def list_for_review(
        self,
        *,
        states: Sequence[str] = ("NEEDS_REVIEW",),
        limit: int = 100,
    ) -> list[ReviewQueueItem]:
        """Worklist for reviewer desk.

        Filter: ``workflow_state IN states`` (default NEEDS_REVIEW only).
        Order: ``created_at ASC, packet_id ASC`` (oldest first — documented policy).
        Not a generic admin query builder.
        """
        state_list = list(states) if states else ["NEEDS_REVIEW"]
        if not state_list:
            return []
        capped = max(1, min(int(limit), 500))
        placeholders = ",".join("?" for _ in state_list)
        try:
            rows = self._conn.execute(
                f"""
                SELECT packet_id, site_ref_id, city, workflow_state, revision,
                       document_json, created_at, updated_at
                FROM observation_packets
                WHERE workflow_state IN ({placeholders})
                ORDER BY created_at ASC, packet_id ASC
                LIMIT ?
                """,
                (*state_list, capped),
            ).fetchall()
        except sqlite3.Error as exc:
            raise PersistenceFailure("failed to list review queue") from exc

        items: list[ReviewQueueItem] = []
        for row in rows:
            doc = loads_document(row["document_json"])
            packet = document_to_packet(doc)
            items.append(_queue_item_from_packet(packet, row))
        return items

    def _insert(
        self,
        *,
        packet_id: str,
        site_ref_id: str,
        city: str,
        workflow_state: str,
        document_json: str,
        flags_rules_version: str | None,
        now: str,
        packet: ObservationPacket,
    ) -> PacketRecord:
        if self.exists(packet_id):
            raise DuplicatePacket(packet_id)
        self._conn.execute(
            """
            INSERT INTO observation_packets (
                packet_id, site_ref_id, city, workflow_state, revision,
                document_json, flags_rules_version, created_at, updated_at,
                observer_ref
            ) VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?, ?)
            """,
            (
                packet_id,
                site_ref_id,
                city,
                workflow_state,
                document_json,
                flags_rules_version,
                now,
                now,
                packet.observer_ref,
            ),
        )
        return PacketRecord(
            packet=packet,
            revision=1,
            created_at=_parse_dt(now),
            updated_at=_parse_dt(now),
        )

    def _update(
        self,
        *,
        packet_id: str,
        site_ref_id: str,
        city: str,
        workflow_state: str,
        document_json: str,
        flags_rules_version: str | None,
        now: str,
        expected_revision: int,
        packet: ObservationPacket,
    ) -> PacketRecord:
        cur = self._conn.execute(
            """
            UPDATE observation_packets
            SET site_ref_id = ?,
                city = ?,
                workflow_state = ?,
                revision = revision + 1,
                document_json = ?,
                flags_rules_version = ?,
                updated_at = ?
            WHERE packet_id = ? AND revision = ?
            """,
            (
                site_ref_id,
                city,
                workflow_state,
                document_json,
                flags_rules_version,
                now,
                packet_id,
                expected_revision,
            ),
        )
        if cur.rowcount == 0:
            if not self.exists(packet_id):
                raise PacketNotFound(packet_id)
            raise ConcurrencyConflict(packet_id, expected_revision)
        row = self._conn.execute(
            """
            SELECT revision, created_at, updated_at
            FROM observation_packets WHERE packet_id = ?
            """,
            (packet_id,),
        ).fetchone()
        assert row is not None
        return PacketRecord(
            packet=packet,
            revision=int(row["revision"]),
            created_at=_parse_dt(row["created_at"]),
            updated_at=_parse_dt(row["updated_at"]),
        )
