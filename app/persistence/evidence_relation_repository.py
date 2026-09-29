"""SQLite EvidenceRelation repository — relational rows, not a graph DB."""

from __future__ import annotations

import sqlite3

from app.application.errors import (
    DuplicateResource,
    PersistenceFailure,
    ResourceNotFound,
)
from app.domain.evidence.relation import EvidenceRelation
from app.persistence._sqlite_errors import raise_integrity
from app.persistence.aquasignal_mapping import (
    evidence_relation_from_row,
    evidence_relation_to_row,
)


class SqliteEvidenceRelationRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get(self, relation_id: str) -> EvidenceRelation | None:
        try:
            row = self._conn.execute(
                """
                SELECT relation_id, relation_type, left_ref, right_ref,
                       analysis_run_id, rationale_code, message
                FROM evidence_relations
                WHERE relation_id = ?
                """,
                (relation_id,),
            ).fetchone()
        except sqlite3.Error as exc:
            raise PersistenceFailure("failed to load evidence_relation") from exc
        if row is None:
            return None
        return evidence_relation_from_row(row)

    def require(self, relation_id: str) -> EvidenceRelation:
        rel = self.get(relation_id)
        if rel is None:
            raise ResourceNotFound("evidence_relation", relation_id)
        return rel

    def exists(self, relation_id: str) -> bool:
        try:
            row = self._conn.execute(
                "SELECT 1 FROM evidence_relations WHERE relation_id = ?",
                (relation_id,),
            ).fetchone()
        except sqlite3.Error as exc:
            raise PersistenceFailure("failed to check evidence_relation") from exc
        return row is not None

    def save(self, relation: EvidenceRelation) -> EvidenceRelation:
        row = evidence_relation_to_row(relation)
        try:
            if self.exists(relation.relation_id):
                self._conn.execute(
                    """
                    UPDATE evidence_relations SET
                        relation_type = ?, left_ref = ?, right_ref = ?,
                        analysis_run_id = ?, rationale_code = ?, message = ?
                    WHERE relation_id = ?
                    """,
                    (
                        row["relation_type"],
                        row["left_ref"],
                        row["right_ref"],
                        row["analysis_run_id"],
                        row["rationale_code"],
                        row["message"],
                        row["relation_id"],
                    ),
                )
            else:
                self._conn.execute(
                    """
                    INSERT INTO evidence_relations (
                        relation_id, relation_type, left_ref, right_ref,
                        analysis_run_id, rationale_code, message
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row["relation_id"],
                        row["relation_type"],
                        row["left_ref"],
                        row["right_ref"],
                        row["analysis_run_id"],
                        row["rationale_code"],
                        row["message"],
                    ),
                )
        except sqlite3.IntegrityError as exc:
            if "UNIQUE" in str(exc).upper() or "PRIMARY" in str(exc).upper():
                raise DuplicateResource("evidence_relation", relation.relation_id) from exc
            raise_integrity(exc, context="evidence_relation.save")
        except sqlite3.Error as exc:
            raise PersistenceFailure("failed to save evidence_relation") from exc
        return self.require(relation.relation_id)

    def list_for_run(self, analysis_run_id: str) -> list[EvidenceRelation]:
        try:
            rows = self._conn.execute(
                """
                SELECT relation_id, relation_type, left_ref, right_ref,
                       analysis_run_id, rationale_code, message
                FROM evidence_relations
                WHERE analysis_run_id = ?
                ORDER BY relation_id ASC
                """,
                (analysis_run_id,),
            ).fetchall()
        except sqlite3.Error as exc:
            raise PersistenceFailure("failed to list evidence_relations for run") from exc
        return [evidence_relation_from_row(r) for r in rows]
