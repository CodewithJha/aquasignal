"""SQLite append-only ProvenanceRepository — no update/delete methods."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Sequence

from app.application.errors import PersistenceFailure, ProvenanceAppendFailure
from app.application.ports import ProvenanceRecord
from app.application.serialization import dumps_json_value, loads_json_value
from app.domain.provenance_port import ProvenanceIntent


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class SqliteProvenanceRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def append(self, intent: ProvenanceIntent) -> ProvenanceRecord:
        return self.append_many([intent])[0]

    def append_many(self, intents: Sequence[ProvenanceIntent]) -> list[ProvenanceRecord]:
        if not intents:
            return []
        stored: list[ProvenanceRecord] = []
        try:
            for intent in intents:
                at_iso = intent.at.isoformat()
                cur = self._conn.execute(
                    """
                    INSERT INTO provenance_events (
                        event_id, packet_id, at, actor_type, actor_id, action,
                        before_json, after_json, model_id, prompt_version,
                        rule_engine_version
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        intent.intent_id,
                        intent.packet_id,
                        at_iso,
                        intent.actor.actor_type.value,
                        intent.actor.actor_id,
                        intent.action,
                        dumps_json_value(intent.before),
                        dumps_json_value(intent.after),
                        intent.model_id,
                        intent.prompt_version,
                        intent.rule_engine_version,
                    ),
                )
                seq = int(cur.lastrowid)
                stored.append(
                    ProvenanceRecord(
                        event_id=intent.intent_id,
                        packet_id=intent.packet_id,
                        seq=seq,
                        at=intent.at,
                        actor_type=intent.actor.actor_type.value,
                        actor_id=intent.actor.actor_id,
                        action=intent.action,
                        before=intent.before,
                        after=intent.after,
                        model_id=intent.model_id,
                        prompt_version=intent.prompt_version,
                        rule_engine_version=intent.rule_engine_version,
                    )
                )
        except sqlite3.Error as exc:
            raise ProvenanceAppendFailure("failed to append provenance") from exc
        return stored

    def list_for_packet(self, packet_id: str) -> list[ProvenanceRecord]:
        try:
            rows = self._conn.execute(
                """
                SELECT seq, event_id, packet_id, at, actor_type, actor_id, action,
                       before_json, after_json, model_id, prompt_version,
                       rule_engine_version
                FROM provenance_events
                WHERE packet_id = ?
                ORDER BY seq ASC
                """,
                (packet_id,),
            ).fetchall()
        except sqlite3.Error as exc:
            raise PersistenceFailure("failed to list provenance") from exc
        return [
            ProvenanceRecord(
                event_id=str(row["event_id"]),
                packet_id=str(row["packet_id"]),
                seq=int(row["seq"]),
                at=_parse_dt(row["at"]),
                actor_type=str(row["actor_type"]),
                actor_id=str(row["actor_id"]),
                action=str(row["action"]),
                before=loads_json_value(row["before_json"]),
                after=loads_json_value(row["after_json"]),
                model_id=row["model_id"],
                prompt_version=row["prompt_version"],
                rule_engine_version=row["rule_engine_version"],
            )
            for row in rows
        ]
