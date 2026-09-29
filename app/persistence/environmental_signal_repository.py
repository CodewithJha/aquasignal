"""SQLite EnvironmentalSignal repository."""

from __future__ import annotations

import sqlite3

from app.application.errors import (
    DuplicateResource,
    PersistenceFailure,
    ResourceNotFound,
)
from app.domain.signal.environmental import EnvironmentalSignal
from app.persistence._sqlite_errors import raise_integrity
from app.persistence.aquasignal_mapping import (
    environmental_signal_from_parts,
    environmental_signal_to_parts,
)


class SqliteEnvironmentalSignalRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def _load_evidence_ids(self, signal_id: str) -> tuple[str, ...]:
        rows = self._conn.execute(
            """
            SELECT evidence_id FROM signal_evidence
            WHERE signal_id = ?
            ORDER BY position ASC
            """,
            (signal_id,),
        ).fetchall()
        return tuple(str(r["evidence_id"]) for r in rows)

    def get(self, signal_id: str) -> EnvironmentalSignal | None:
        try:
            row = self._conn.execute(
                """
                SELECT signal_id, detector_id, detector_version, signal_type,
                       site_id, city, display_name, lat, lon,
                       fhir_location_identifier, window_start, window_end,
                       summary, metrics_json, explanation_json, analysis_run_id
                FROM environmental_signals
                WHERE signal_id = ?
                """,
                (signal_id,),
            ).fetchone()
            if row is None:
                return None
            evidence_ids = self._load_evidence_ids(signal_id)
        except sqlite3.Error as exc:
            raise PersistenceFailure("failed to load environmental_signal") from exc
        return environmental_signal_from_parts(row, evidence_ids)

    def require(self, signal_id: str) -> EnvironmentalSignal:
        signal = self.get(signal_id)
        if signal is None:
            raise ResourceNotFound("environmental_signal", signal_id)
        return signal

    def exists(self, signal_id: str) -> bool:
        try:
            row = self._conn.execute(
                "SELECT 1 FROM environmental_signals WHERE signal_id = ?",
                (signal_id,),
            ).fetchone()
        except sqlite3.Error as exc:
            raise PersistenceFailure("failed to check environmental_signal") from exc
        return row is not None

    def save(self, signal: EnvironmentalSignal) -> EnvironmentalSignal:
        row, evidence_ids = environmental_signal_to_parts(signal)
        try:
            if self.exists(signal.signal_id):
                self._conn.execute(
                    """
                    UPDATE environmental_signals SET
                        detector_id = ?, detector_version = ?, signal_type = ?,
                        site_id = ?, city = ?, display_name = ?, lat = ?, lon = ?,
                        fhir_location_identifier = ?, window_start = ?, window_end = ?,
                        summary = ?, metrics_json = ?, explanation_json = ?,
                        analysis_run_id = ?
                    WHERE signal_id = ?
                    """,
                    (
                        row["detector_id"],
                        row["detector_version"],
                        row["signal_type"],
                        row["site_id"],
                        row["city"],
                        row["display_name"],
                        row["lat"],
                        row["lon"],
                        row["fhir_location_identifier"],
                        row["window_start"],
                        row["window_end"],
                        row["summary"],
                        row["metrics_json"],
                        row["explanation_json"],
                        row["analysis_run_id"],
                        row["signal_id"],
                    ),
                )
                self._conn.execute(
                    "DELETE FROM signal_evidence WHERE signal_id = ?",
                    (signal.signal_id,),
                )
            else:
                self._conn.execute(
                    """
                    INSERT INTO environmental_signals (
                        signal_id, detector_id, detector_version, signal_type,
                        site_id, city, display_name, lat, lon,
                        fhir_location_identifier, window_start, window_end,
                        summary, metrics_json, explanation_json, analysis_run_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row["signal_id"],
                        row["detector_id"],
                        row["detector_version"],
                        row["signal_type"],
                        row["site_id"],
                        row["city"],
                        row["display_name"],
                        row["lat"],
                        row["lon"],
                        row["fhir_location_identifier"],
                        row["window_start"],
                        row["window_end"],
                        row["summary"],
                        row["metrics_json"],
                        row["explanation_json"],
                        row["analysis_run_id"],
                    ),
                )
            for pos, eid in enumerate(evidence_ids):
                self._conn.execute(
                    """
                    INSERT INTO signal_evidence (signal_id, position, evidence_id)
                    VALUES (?, ?, ?)
                    """,
                    (signal.signal_id, pos, eid),
                )
        except sqlite3.IntegrityError as exc:
            if "UNIQUE" in str(exc).upper() or "PRIMARY" in str(exc).upper():
                raise DuplicateResource("environmental_signal", signal.signal_id) from exc
            raise_integrity(exc, context="environmental_signal.save")
        except sqlite3.Error as exc:
            raise PersistenceFailure("failed to save environmental_signal") from exc
        return self.require(signal.signal_id)

    def list_for_run(self, analysis_run_id: str) -> list[EnvironmentalSignal]:
        try:
            rows = self._conn.execute(
                """
                SELECT signal_id FROM environmental_signals
                WHERE analysis_run_id = ?
                ORDER BY signal_id ASC
                """,
                (analysis_run_id,),
            ).fetchall()
        except sqlite3.Error as exc:
            raise PersistenceFailure("failed to list signals for run") from exc
        return [self.require(str(r["signal_id"])) for r in rows]

    def list_evidence_ids(self, signal_id: str) -> list[str]:
        """Query helper: evidence ids linked to a signal (ordered)."""
        try:
            return list(self._load_evidence_ids(signal_id))
        except sqlite3.Error as exc:
            raise PersistenceFailure("failed to list evidence for signal") from exc
