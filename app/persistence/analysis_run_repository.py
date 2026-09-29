"""SQLite AnalysisRun repository — STARTED→SUCCEEDED|FAILED; no silent success overwrite."""

from __future__ import annotations

import sqlite3

from app.application.errors import (
    DuplicateResource,
    ImmutableAnalysisRun,
    PersistenceFailure,
    ResourceNotFound,
)
from app.domain.investigation.analysis_run import AnalysisRun
from app.domain.investigation.enums import AnalysisRunStatus
from app.persistence._sqlite_errors import raise_integrity
from app.persistence.aquasignal_mapping import analysis_run_from_parts, analysis_run_to_row

_SELECT_COLS = """
    run_id, started_at, finished_at, status, snapshot_hash,
    detector_set_version, parameters_hash, error,
    site_id, window_start, window_end
"""


class SqliteAnalysisRunRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def _load_signal_ids(self, run_id: str) -> tuple[str, ...]:
        rows = self._conn.execute(
            """
            SELECT signal_id FROM analysis_run_signals
            WHERE run_id = ?
            ORDER BY position ASC
            """,
            (run_id,),
        ).fetchall()
        return tuple(str(r["signal_id"]) for r in rows)

    def _status(self, run_id: str) -> AnalysisRunStatus | None:
        row = self._conn.execute(
            "SELECT status FROM analysis_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        if row is None:
            return None
        return AnalysisRunStatus(str(row["status"]))

    def get(self, run_id: str) -> AnalysisRun | None:
        try:
            row = self._conn.execute(
                f"""
                SELECT {_SELECT_COLS}
                FROM analysis_runs
                WHERE run_id = ?
                """,
                (run_id,),
            ).fetchone()
            if row is None:
                return None
            signals = self._load_signal_ids(run_id)
        except sqlite3.Error as exc:
            raise PersistenceFailure("failed to load analysis_run") from exc
        return analysis_run_from_parts(row, signals)

    def require(self, run_id: str) -> AnalysisRun:
        run = self.get(run_id)
        if run is None:
            raise ResourceNotFound("analysis_run", run_id)
        return run

    def exists(self, run_id: str) -> bool:
        try:
            row = self._conn.execute(
                "SELECT 1 FROM analysis_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        except sqlite3.Error as exc:
            raise PersistenceFailure("failed to check analysis_run") from exc
        return row is not None

    def _replace_signals(self, run_id: str, signal_ids: tuple[str, ...]) -> None:
        self._conn.execute(
            "DELETE FROM analysis_run_signals WHERE run_id = ?",
            (run_id,),
        )
        for pos, sid in enumerate(signal_ids):
            self._conn.execute(
                """
                INSERT INTO analysis_run_signals (run_id, position, signal_id)
                VALUES (?, ?, ?)
                """,
                (run_id, pos, sid),
            )

    def save(self, run: AnalysisRun) -> AnalysisRun:
        row = analysis_run_to_row(run)
        try:
            current = self._status(run.run_id)
            if current is AnalysisRunStatus.SUCCEEDED:
                raise ImmutableAnalysisRun(run.run_id)
            if current is None:
                self._conn.execute(
                    """
                    INSERT INTO analysis_runs (
                        run_id, started_at, finished_at, status, snapshot_hash,
                        detector_set_version, parameters_hash, error,
                        site_id, window_start, window_end
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row["run_id"],
                        row["started_at"],
                        row["finished_at"],
                        row["status"],
                        row["snapshot_hash"],
                        row["detector_set_version"],
                        row["parameters_hash"],
                        row["error"],
                        row["site_id"],
                        row["window_start"],
                        row["window_end"],
                    ),
                )
            else:
                if current is AnalysisRunStatus.FAILED:
                    raise ImmutableAnalysisRun(run.run_id)
                self._conn.execute(
                    """
                    UPDATE analysis_runs SET
                        started_at = ?, finished_at = ?, status = ?,
                        snapshot_hash = ?, detector_set_version = ?,
                        parameters_hash = ?, error = ?,
                        site_id = ?, window_start = ?, window_end = ?
                    WHERE run_id = ?
                    """,
                    (
                        row["started_at"],
                        row["finished_at"],
                        row["status"],
                        row["snapshot_hash"],
                        row["detector_set_version"],
                        row["parameters_hash"],
                        row["error"],
                        row["site_id"],
                        row["window_start"],
                        row["window_end"],
                        row["run_id"],
                    ),
                )
            self._replace_signals(run.run_id, run.signals_produced)
        except ImmutableAnalysisRun:
            raise
        except sqlite3.IntegrityError as exc:
            if "UNIQUE" in str(exc).upper() or "PRIMARY" in str(exc).upper():
                raise DuplicateResource("analysis_run", run.run_id) from exc
            raise_integrity(exc, context="analysis_run.save")
        except sqlite3.Error as exc:
            raise PersistenceFailure("failed to save analysis_run") from exc
        return self.require(run.run_id)

    def list_for_snapshot_hash(self, snapshot_hash: str) -> list[AnalysisRun]:
        try:
            rows = self._conn.execute(
                """
                SELECT run_id FROM analysis_runs
                WHERE snapshot_hash = ?
                ORDER BY started_at ASC, run_id ASC
                """,
                (snapshot_hash,),
            ).fetchall()
        except sqlite3.Error as exc:
            raise PersistenceFailure("failed to list analysis_runs for snapshot") from exc
        return [self.require(str(r["run_id"])) for r in rows]

    def list_for_site(self, site_id: str) -> list[AnalysisRun]:
        """Runs scoped to site_id (A6 self-describing). Newest first.

        Includes SUCCEEDED runs with zero signals (no-signal success).
        Falls back to snapshot membership for pre-A6 rows with empty site_id.
        """
        try:
            rows = self._conn.execute(
                """
                SELECT run_id, started_at FROM (
                    SELECT ar.run_id AS run_id, ar.started_at AS started_at
                    FROM analysis_runs AS ar
                    WHERE ar.site_id = ?
                    UNION
                    SELECT DISTINCT ar.run_id AS run_id, ar.started_at AS started_at
                    FROM analysis_runs AS ar
                    INNER JOIN evidence_snapshots AS es
                        ON es.snapshot_hash = ar.snapshot_hash
                    INNER JOIN evidence_snapshot_members AS m
                        ON m.snapshot_id = es.snapshot_id
                    INNER JOIN evidence_items AS ei
                        ON ei.evidence_id = m.evidence_id
                    WHERE (ar.site_id IS NULL OR ar.site_id = '')
                      AND ei.site_id = ?
                ) AS site_runs
                ORDER BY started_at DESC, run_id DESC
                """,
                (site_id, site_id),
            ).fetchall()
        except sqlite3.Error as exc:
            raise PersistenceFailure("failed to list analysis_runs for site") from exc
        return [self.require(str(r["run_id"])) for r in rows]

    def list_signal_ids(self, run_id: str) -> list[str]:
        try:
            return list(self._load_signal_ids(run_id))
        except sqlite3.Error as exc:
            raise PersistenceFailure("failed to list signals for run") from exc
