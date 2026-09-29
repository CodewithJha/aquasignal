"""SQLite EvidenceSnapshot repository — ordered members + hash round-trip."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from app.application.errors import (
    DuplicateResource,
    PersistenceFailure,
    ResourceNotFound,
)
from app.domain.evidence.snapshot import EvidenceSnapshot
from app.persistence._sqlite_errors import raise_integrity
from app.persistence.aquasignal_mapping import (
    evidence_snapshot_from_parts,
    evidence_snapshot_to_parts,
)


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class SqliteEvidenceSnapshotRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def _load_ordered_ids(self, snapshot_id: str) -> tuple[str, ...]:
        rows = self._conn.execute(
            """
            SELECT evidence_id FROM evidence_snapshot_members
            WHERE snapshot_id = ?
            ORDER BY position ASC
            """,
            (snapshot_id,),
        ).fetchall()
        return tuple(str(r["evidence_id"]) for r in rows)

    def get(self, snapshot_id: str) -> EvidenceSnapshot | None:
        try:
            row = self._conn.execute(
                """
                SELECT snapshot_id, snapshot_hash, created_at, source_manifest_json
                FROM evidence_snapshots
                WHERE snapshot_id = ?
                """,
                (snapshot_id,),
            ).fetchone()
            if row is None:
                return None
            ids = self._load_ordered_ids(snapshot_id)
        except sqlite3.Error as exc:
            raise PersistenceFailure("failed to load evidence_snapshot") from exc
        return evidence_snapshot_from_parts(row, ids)

    def require(self, snapshot_id: str) -> EvidenceSnapshot:
        snap = self.get(snapshot_id)
        if snap is None:
            raise ResourceNotFound("evidence_snapshot", snapshot_id)
        return snap

    def exists(self, snapshot_id: str) -> bool:
        try:
            row = self._conn.execute(
                "SELECT 1 FROM evidence_snapshots WHERE snapshot_id = ?",
                (snapshot_id,),
            ).fetchone()
        except sqlite3.Error as exc:
            raise PersistenceFailure("failed to check evidence_snapshot") from exc
        return row is not None

    def save(self, snapshot: EvidenceSnapshot) -> EvidenceSnapshot:
        row, ordered_ids = evidence_snapshot_to_parts(snapshot)
        try:
            if self.exists(snapshot.snapshot_id):
                self._conn.execute(
                    """
                    UPDATE evidence_snapshots
                    SET snapshot_hash = ?, created_at = ?, source_manifest_json = ?
                    WHERE snapshot_id = ?
                    """,
                    (
                        row["snapshot_hash"],
                        row["created_at"],
                        row["source_manifest_json"],
                        row["snapshot_id"],
                    ),
                )
                self._conn.execute(
                    "DELETE FROM evidence_snapshot_members WHERE snapshot_id = ?",
                    (snapshot.snapshot_id,),
                )
            else:
                self._conn.execute(
                    """
                    INSERT INTO evidence_snapshots (
                        snapshot_id, snapshot_hash, created_at, source_manifest_json
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (
                        row["snapshot_id"],
                        row["snapshot_hash"],
                        row["created_at"],
                        row["source_manifest_json"],
                    ),
                )
            for pos, eid in enumerate(ordered_ids):
                self._conn.execute(
                    """
                    INSERT INTO evidence_snapshot_members (
                        snapshot_id, position, evidence_id
                    ) VALUES (?, ?, ?)
                    """,
                    (snapshot.snapshot_id, pos, eid),
                )
        except sqlite3.IntegrityError as exc:
            if "UNIQUE" in str(exc).upper() or "PRIMARY" in str(exc).upper():
                raise DuplicateResource("evidence_snapshot", snapshot.snapshot_id) from exc
            raise_integrity(exc, context="evidence_snapshot.save")
        except sqlite3.Error as exc:
            raise PersistenceFailure("failed to save evidence_snapshot") from exc
        return self.require(snapshot.snapshot_id)

    def find_for_hash(
        self, snapshot_hash: str, *, near: datetime | None = None
    ) -> EvidenceSnapshot | None:
        """Resolve a snapshot for an AnalysisRun's snapshot_hash.

        When multiple snapshots share a hash (append-only re-runs), prefer the
        row whose created_at is closest to ``near`` (typically run.started_at).
        """
        try:
            rows = self._conn.execute(
                """
                SELECT snapshot_id, created_at FROM evidence_snapshots
                WHERE snapshot_hash = ?
                ORDER BY created_at ASC, snapshot_id ASC
                """,
                (snapshot_hash,),
            ).fetchall()
        except sqlite3.Error as exc:
            raise PersistenceFailure("failed to find evidence_snapshot by hash") from exc
        if not rows:
            return None
        if near is None or len(rows) == 1:
            return self.require(str(rows[-1]["snapshot_id"]))
        best_id = str(rows[0]["snapshot_id"])
        best_delta = abs((_parse_dt(str(rows[0]["created_at"])) - near).total_seconds())
        for row in rows[1:]:
            delta = abs((_parse_dt(str(row["created_at"])) - near).total_seconds())
            if delta <= best_delta:
                best_delta = delta
                best_id = str(row["snapshot_id"])
        return self.require(best_id)
