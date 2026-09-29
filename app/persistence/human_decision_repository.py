"""SQLite HumanDecision repository — reuses Actor; no auth."""

from __future__ import annotations

import sqlite3

from app.application.errors import (
    DuplicateResource,
    PersistenceFailure,
    ResourceNotFound,
)
from app.domain.investigation.decision import HumanDecision
from app.persistence._sqlite_errors import raise_integrity
from app.persistence.aquasignal_mapping import (
    human_decision_from_parts,
    human_decision_to_parts,
)


class SqliteHumanDecisionRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def _load_linked_signals(self, decision_id: str) -> tuple[str, ...]:
        rows = self._conn.execute(
            """
            SELECT signal_id FROM decision_signals
            WHERE decision_id = ?
            ORDER BY position ASC
            """,
            (decision_id,),
        ).fetchall()
        return tuple(str(r["signal_id"]) for r in rows)

    def get(self, decision_id: str) -> HumanDecision | None:
        try:
            row = self._conn.execute(
                """
                SELECT decision_id, case_id, actor_type, actor_id, decided_at,
                       decision_code, rationale
                FROM human_decisions
                WHERE decision_id = ?
                """,
                (decision_id,),
            ).fetchone()
            if row is None:
                return None
            linked = self._load_linked_signals(decision_id)
        except sqlite3.Error as exc:
            raise PersistenceFailure("failed to load human_decision") from exc
        return human_decision_from_parts(row, linked)

    def require(self, decision_id: str) -> HumanDecision:
        decision = self.get(decision_id)
        if decision is None:
            raise ResourceNotFound("human_decision", decision_id)
        return decision

    def exists(self, decision_id: str) -> bool:
        try:
            row = self._conn.execute(
                "SELECT 1 FROM human_decisions WHERE decision_id = ?",
                (decision_id,),
            ).fetchone()
        except sqlite3.Error as exc:
            raise PersistenceFailure("failed to check human_decision") from exc
        return row is not None

    def save(self, decision: HumanDecision) -> HumanDecision:
        row, linked = human_decision_to_parts(decision)
        try:
            if self.exists(decision.decision_id):
                self._conn.execute(
                    """
                    UPDATE human_decisions SET
                        case_id = ?, actor_type = ?, actor_id = ?, decided_at = ?,
                        decision_code = ?, rationale = ?
                    WHERE decision_id = ?
                    """,
                    (
                        row["case_id"],
                        row["actor_type"],
                        row["actor_id"],
                        row["decided_at"],
                        row["decision_code"],
                        row["rationale"],
                        row["decision_id"],
                    ),
                )
                self._conn.execute(
                    "DELETE FROM decision_signals WHERE decision_id = ?",
                    (decision.decision_id,),
                )
            else:
                self._conn.execute(
                    """
                    INSERT INTO human_decisions (
                        decision_id, case_id, actor_type, actor_id, decided_at,
                        decision_code, rationale
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row["decision_id"],
                        row["case_id"],
                        row["actor_type"],
                        row["actor_id"],
                        row["decided_at"],
                        row["decision_code"],
                        row["rationale"],
                    ),
                )
            for pos, sid in enumerate(linked):
                self._conn.execute(
                    """
                    INSERT INTO decision_signals (decision_id, position, signal_id)
                    VALUES (?, ?, ?)
                    """,
                    (decision.decision_id, pos, sid),
                )
        except sqlite3.IntegrityError as exc:
            if "UNIQUE" in str(exc).upper() or "PRIMARY" in str(exc).upper():
                raise DuplicateResource("human_decision", decision.decision_id) from exc
            raise_integrity(exc, context="human_decision.save")
        except sqlite3.Error as exc:
            raise PersistenceFailure("failed to save human_decision") from exc
        return self.require(decision.decision_id)

    def list_for_case(self, case_id: str) -> list[HumanDecision]:
        try:
            rows = self._conn.execute(
                """
                SELECT decision_id FROM human_decisions
                WHERE case_id = ?
                ORDER BY decided_at ASC, decision_id ASC
                """,
                (case_id,),
            ).fetchall()
        except sqlite3.Error as exc:
            raise PersistenceFailure("failed to list human_decisions for case") from exc
        return [self.require(str(r["decision_id"])) for r in rows]
