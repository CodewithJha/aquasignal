"""SQLite InvestigationCase repository — versioned optimistic concurrency."""

from __future__ import annotations

import sqlite3

from app.application.errors import (
    ConcurrencyConflict,
    DuplicateResource,
    PersistenceFailure,
    ResourceNotFound,
)
from app.application.ports import CaseRecord
from app.domain.investigation.case import InvestigationCase
from app.persistence._sqlite_errors import raise_integrity
from app.persistence.aquasignal_mapping import (
    investigation_case_from_parts,
    investigation_case_to_row,
)


class SqliteInvestigationCaseRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def _load_signal_ids(self, case_id: str) -> tuple[str, ...]:
        rows = self._conn.execute(
            """
            SELECT signal_id FROM case_signals
            WHERE case_id = ?
            ORDER BY position ASC
            """,
            (case_id,),
        ).fetchall()
        return tuple(str(r["signal_id"]) for r in rows)

    def _load_decision_ids(self, case_id: str) -> tuple[str, ...]:
        rows = self._conn.execute(
            """
            SELECT decision_id FROM case_decisions
            WHERE case_id = ?
            ORDER BY position ASC
            """,
            (case_id,),
        ).fetchall()
        return tuple(str(r["decision_id"]) for r in rows)

    def get(self, case_id: str) -> CaseRecord | None:
        try:
            row = self._conn.execute(
                """
                SELECT case_id, site_id, city, display_name, lat, lon,
                       fhir_location_identifier, window_start, window_end,
                       analysis_run_id, reproducibility_ref, opened_at, state,
                       version
                FROM investigation_cases
                WHERE case_id = ?
                """,
                (case_id,),
            ).fetchone()
            if row is None:
                return None
            signals = self._load_signal_ids(case_id)
            decisions = self._load_decision_ids(case_id)
        except sqlite3.Error as exc:
            raise PersistenceFailure("failed to load investigation_case") from exc
        case = investigation_case_from_parts(row, signals, decisions)
        return CaseRecord(case=case, version=int(row["version"]))

    def require(self, case_id: str) -> CaseRecord:
        record = self.get(case_id)
        if record is None:
            raise ResourceNotFound("investigation_case", case_id)
        return record

    def exists(self, case_id: str) -> bool:
        try:
            row = self._conn.execute(
                "SELECT 1 FROM investigation_cases WHERE case_id = ?",
                (case_id,),
            ).fetchone()
        except sqlite3.Error as exc:
            raise PersistenceFailure("failed to check investigation_case") from exc
        return row is not None

    def _replace_links(
        self,
        case_id: str,
        signal_ids: tuple[str, ...],
        decision_ids: tuple[str, ...],
    ) -> None:
        self._conn.execute("DELETE FROM case_signals WHERE case_id = ?", (case_id,))
        self._conn.execute("DELETE FROM case_decisions WHERE case_id = ?", (case_id,))
        for pos, sid in enumerate(signal_ids):
            self._conn.execute(
                """
                INSERT INTO case_signals (case_id, position, signal_id)
                VALUES (?, ?, ?)
                """,
                (case_id, pos, sid),
            )
        for pos, did in enumerate(decision_ids):
            self._conn.execute(
                """
                INSERT INTO case_decisions (case_id, position, decision_id)
                VALUES (?, ?, ?)
                """,
                (case_id, pos, did),
            )

    def save(
        self, case: InvestigationCase, *, expected_version: int
    ) -> CaseRecord:
        """Insert when expected_version==0; else OCC update like packets."""
        row = investigation_case_to_row(case)
        try:
            if expected_version == 0:
                if self.exists(case.case_id):
                    raise DuplicateResource("investigation_case", case.case_id)
                self._conn.execute(
                    """
                    INSERT INTO investigation_cases (
                        case_id, site_id, city, display_name, lat, lon,
                        fhir_location_identifier, window_start, window_end,
                        analysis_run_id, reproducibility_ref, opened_at, state,
                        version
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                    """,
                    (
                        row["case_id"],
                        row["site_id"],
                        row["city"],
                        row["display_name"],
                        row["lat"],
                        row["lon"],
                        row["fhir_location_identifier"],
                        row["window_start"],
                        row["window_end"],
                        row["analysis_run_id"],
                        row["reproducibility_ref"],
                        row["opened_at"],
                        row["state"],
                    ),
                )
                self._replace_links(case.case_id, case.signal_ids, case.decision_ids)
                return CaseRecord(case=case, version=1)

            cur = self._conn.execute(
                """
                UPDATE investigation_cases SET
                    site_id = ?, city = ?, display_name = ?, lat = ?, lon = ?,
                    fhir_location_identifier = ?, window_start = ?, window_end = ?,
                    analysis_run_id = ?, reproducibility_ref = ?, opened_at = ?,
                    state = ?, version = version + 1
                WHERE case_id = ? AND version = ?
                """,
                (
                    row["site_id"],
                    row["city"],
                    row["display_name"],
                    row["lat"],
                    row["lon"],
                    row["fhir_location_identifier"],
                    row["window_start"],
                    row["window_end"],
                    row["analysis_run_id"],
                    row["reproducibility_ref"],
                    row["opened_at"],
                    row["state"],
                    case.case_id,
                    expected_version,
                ),
            )
            if cur.rowcount == 0:
                if not self.exists(case.case_id):
                    raise ResourceNotFound("investigation_case", case.case_id)
                raise ConcurrencyConflict(case.case_id, expected_version)
            self._replace_links(case.case_id, case.signal_ids, case.decision_ids)
            ver_row = self._conn.execute(
                "SELECT version FROM investigation_cases WHERE case_id = ?",
                (case.case_id,),
            ).fetchone()
            assert ver_row is not None
            return CaseRecord(case=case, version=int(ver_row["version"]))
        except (DuplicateResource, ResourceNotFound, ConcurrencyConflict):
            raise
        except sqlite3.IntegrityError as exc:
            if expected_version == 0 and (
                "UNIQUE" in str(exc).upper() or "PRIMARY" in str(exc).upper()
            ):
                raise DuplicateResource("investigation_case", case.case_id) from exc
            raise_integrity(exc, context="investigation_case.save")
        except sqlite3.Error as exc:
            raise PersistenceFailure("failed to save investigation_case") from exc

    def list_for_site(self, site_id: str) -> list[CaseRecord]:
        try:
            rows = self._conn.execute(
                """
                SELECT case_id FROM investigation_cases
                WHERE site_id = ?
                ORDER BY opened_at ASC, case_id ASC
                """,
                (site_id,),
            ).fetchall()
        except sqlite3.Error as exc:
            raise PersistenceFailure("failed to list investigation_cases for site") from exc
        return [self.require(str(r["case_id"])) for r in rows]

    def find_active_for_run(self, analysis_run_id: str) -> CaseRecord | None:
        """Oldest OPEN / UNDER_REVIEW case for the run, if any."""
        try:
            row = self._conn.execute(
                """
                SELECT case_id FROM investigation_cases
                WHERE analysis_run_id = ? AND state IN ('OPEN', 'UNDER_REVIEW')
                ORDER BY opened_at ASC, case_id ASC
                LIMIT 1
                """,
                (analysis_run_id,),
            ).fetchone()
        except sqlite3.Error as exc:
            raise PersistenceFailure("failed to find active case for run") from exc
        return None if row is None else self.require(str(row["case_id"]))

    def list_signal_ids(self, case_id: str) -> list[str]:
        try:
            return list(self._load_signal_ids(case_id))
        except sqlite3.Error as exc:
            raise PersistenceFailure("failed to list signals for case") from exc
