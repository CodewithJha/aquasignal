"""SQLite UnitOfWork — ConfirmGate + AquaSignal repos share one transaction."""

from __future__ import annotations

import sqlite3

from app.application.errors import PersistenceFailure
from app.persistence.analysis_run_repository import SqliteAnalysisRunRepository
from app.persistence.environmental_signal_repository import (
    SqliteEnvironmentalSignalRepository,
)
from app.persistence.evidence_item_repository import SqliteEvidenceItemRepository
from app.persistence.evidence_relation_repository import SqliteEvidenceRelationRepository
from app.persistence.evidence_snapshot_repository import SqliteEvidenceSnapshotRepository
from app.persistence.human_decision_repository import SqliteHumanDecisionRepository
from app.persistence.investigation_case_repository import (
    SqliteInvestigationCaseRepository,
)
from app.persistence.packet_repository import SqlitePacketRepository
from app.persistence.provenance_repository import SqliteProvenanceRepository


class SqliteUnitOfWork:
    """One transaction on one connection.

    With ``owns_connection=True`` (the factory default) the connection is
    closed when the ``with`` block exits, so nothing leaks across requests.
    """

    def __init__(self, conn: sqlite3.Connection, *, owns_connection: bool = False) -> None:
        self._conn = conn
        self._owns_connection = owns_connection
        # ConfirmGate
        self.packets = SqlitePacketRepository(conn)
        self.provenance = SqliteProvenanceRepository(conn)
        # AquaSignal A2
        self.evidence_items = SqliteEvidenceItemRepository(conn)
        self.evidence_snapshots = SqliteEvidenceSnapshotRepository(conn)
        self.evidence_relations = SqliteEvidenceRelationRepository(conn)
        self.environmental_signals = SqliteEnvironmentalSignalRepository(conn)
        self.analysis_runs = SqliteAnalysisRunRepository(conn)
        self.investigation_cases = SqliteInvestigationCaseRepository(conn)
        self.human_decisions = SqliteHumanDecisionRepository(conn)
        self._committed = False
        self._entered = False

    def __enter__(self) -> SqliteUnitOfWork:
        self._entered = True
        self._committed = False
        # IMMEDIATE takes the write lock up front so read-then-write (OCC)
        # transactions wait on busy_timeout instead of failing mid-way.
        try:
            self._conn.execute("BEGIN IMMEDIATE")
        except sqlite3.Error as exc:
            self._close_if_owned()
            raise PersistenceFailure("failed to begin transaction") from exc
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            if not self._committed:
                self.rollback()
        finally:
            self._entered = False
            self._close_if_owned()

    def _close_if_owned(self) -> None:
        if self._owns_connection:
            self._conn.close()

    def commit(self) -> None:
        try:
            self._conn.commit()
            self._committed = True
        except sqlite3.Error as exc:
            self.rollback()
            raise PersistenceFailure("failed to commit transaction") from exc

    def rollback(self) -> None:
        try:
            self._conn.rollback()
        except sqlite3.Error as exc:
            raise PersistenceFailure("failed to rollback transaction") from exc
        finally:
            self._committed = False
