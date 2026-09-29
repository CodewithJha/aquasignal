"""SQLite EvidenceItem repository."""

from __future__ import annotations

import sqlite3

from app.application.errors import (
    DuplicateResource,
    PersistenceFailure,
    ResourceNotFound,
)
from app.domain.evidence.item import EvidenceItem
from app.persistence._sqlite_errors import raise_integrity
from app.persistence.aquasignal_mapping import evidence_item_from_row, evidence_item_to_row

_SELECT_COLS = """
    evidence_id, source_class, site_id, city, display_name,
    lat, lon, fhir_location_identifier, observed_at,
    payload_ref, content_hash, license_tag, is_synthetic, fields_json
"""


class SqliteEvidenceItemRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get(self, evidence_id: str) -> EvidenceItem | None:
        try:
            row = self._conn.execute(
                f"""
                SELECT {_SELECT_COLS}
                FROM evidence_items
                WHERE evidence_id = ?
                """,
                (evidence_id,),
            ).fetchone()
        except sqlite3.Error as exc:
            raise PersistenceFailure("failed to load evidence_item") from exc
        if row is None:
            return None
        return evidence_item_from_row(row)

    def require(self, evidence_id: str) -> EvidenceItem:
        item = self.get(evidence_id)
        if item is None:
            raise ResourceNotFound("evidence_item", evidence_id)
        return item

    def exists(self, evidence_id: str) -> bool:
        try:
            row = self._conn.execute(
                "SELECT 1 FROM evidence_items WHERE evidence_id = ?",
                (evidence_id,),
            ).fetchone()
        except sqlite3.Error as exc:
            raise PersistenceFailure("failed to check evidence_item") from exc
        return row is not None

    def save(self, item: EvidenceItem) -> EvidenceItem:
        row = evidence_item_to_row(item)
        try:
            if self.exists(item.evidence_id):
                self._conn.execute(
                    """
                    UPDATE evidence_items SET
                        source_class = ?, site_id = ?, city = ?, display_name = ?,
                        lat = ?, lon = ?, fhir_location_identifier = ?,
                        observed_at = ?, payload_ref = ?, content_hash = ?,
                        license_tag = ?, is_synthetic = ?, fields_json = ?
                    WHERE evidence_id = ?
                    """,
                    (
                        row["source_class"],
                        row["site_id"],
                        row["city"],
                        row["display_name"],
                        row["lat"],
                        row["lon"],
                        row["fhir_location_identifier"],
                        row["observed_at"],
                        row["payload_ref"],
                        row["content_hash"],
                        row["license_tag"],
                        row["is_synthetic"],
                        row["fields_json"],
                        row["evidence_id"],
                    ),
                )
            else:
                self._conn.execute(
                    """
                    INSERT INTO evidence_items (
                        evidence_id, source_class, site_id, city, display_name,
                        lat, lon, fhir_location_identifier, observed_at,
                        payload_ref, content_hash, license_tag, is_synthetic,
                        fields_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row["evidence_id"],
                        row["source_class"],
                        row["site_id"],
                        row["city"],
                        row["display_name"],
                        row["lat"],
                        row["lon"],
                        row["fhir_location_identifier"],
                        row["observed_at"],
                        row["payload_ref"],
                        row["content_hash"],
                        row["license_tag"],
                        row["is_synthetic"],
                        row["fields_json"],
                    ),
                )
        except sqlite3.IntegrityError as exc:
            if "UNIQUE" in str(exc).upper() or "PRIMARY" in str(exc).upper():
                raise DuplicateResource("evidence_item", item.evidence_id) from exc
            raise_integrity(exc, context="evidence_item.save")
        except sqlite3.Error as exc:
            raise PersistenceFailure("failed to save evidence_item") from exc
        return self.require(item.evidence_id)

    def list_for_site(self, site_id: str) -> list[EvidenceItem]:
        try:
            rows = self._conn.execute(
                f"""
                SELECT {_SELECT_COLS}
                FROM evidence_items
                WHERE site_id = ?
                ORDER BY observed_at ASC, evidence_id ASC
                """,
                (site_id,),
            ).fetchall()
        except sqlite3.Error as exc:
            raise PersistenceFailure("failed to list evidence_items for site") from exc
        return [evidence_item_from_row(r) for r in rows]
