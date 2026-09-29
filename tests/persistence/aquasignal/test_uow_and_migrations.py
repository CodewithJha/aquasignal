"""AquaSignal A2 — UoW atomicity + migration coexistence with ConfirmGate."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.application.errors import PersistenceFailure
from app.application.service import ObservationService
from app.domain.packet import ObservationPacket
from app.domain.value_objects import Actor
from app.persistence.factory import open_unit_of_work
from app.persistence.migrations_runner import apply_migrations, list_migration_files
from app.persistence.unit_of_work import SqliteUnitOfWork
from tests.db import make_settings, sqlite_only
from tests.persistence.aquasignal.conftest import (
    make_fixture_evidence,
    make_packet_evidence,
    make_relation,
    make_run,
    make_signal,
    make_snapshot,
)
from tests.persistence.conftest import foam


def test_uow_commit_atomic_snapshot_run_signals_relations(
    uow_factory, coimbra, observed_at, window
) -> None:
    e1 = make_packet_evidence(coimbra, observed_at, eid="ev_u1")
    e2 = make_fixture_evidence(coimbra, observed_at, eid="ev_u2")
    snap = make_snapshot(("ev_u1", "ev_u2"), sid="snap_uow")
    run = make_run(snapshot_hash=snap.snapshot_hash, run_id="run_uow")
    signal = make_signal(
        site=coimbra,
        window=window,
        run_id=run.run_id,
        evidence_ids=("ev_u1", "ev_u2"),
        signal_id="sig_uow",
    )
    rel = make_relation(
        run_id=run.run_id, left="ev_u1", right="sig_uow", rid="rel_uow"
    )

    with uow_factory() as uow:
        uow.evidence_items.save(e1)
        uow.evidence_items.save(e2)
        uow.evidence_snapshots.save(snap)
        uow.analysis_runs.save(run)
        uow.environmental_signals.save(signal)
        run.succeed(signals_produced=("sig_uow",))
        uow.analysis_runs.save(run)
        uow.evidence_relations.save(rel)
        uow.commit()

    with uow_factory() as uow:
        assert uow.evidence_snapshots.require("snap_uow").snapshot_hash == snap.snapshot_hash
        assert uow.analysis_runs.require("run_uow").status.value == "SUCCEEDED"
        assert uow.environmental_signals.require("sig_uow").evidence_ids == (
            "ev_u1",
            "ev_u2",
        )
        assert uow.evidence_relations.require("rel_uow").analysis_run_id == "run_uow"
        uow.commit()


def test_uow_rollback_on_intentional_failure(
    uow_factory, coimbra, observed_at, window
) -> None:
    e1 = make_packet_evidence(coimbra, observed_at, eid="ev_rb1")
    snap = make_snapshot(("ev_rb1",), sid="snap_rb")
    run = make_run(snapshot_hash=snap.snapshot_hash, run_id="run_rb")

    class BoomUow(SqliteUnitOfWork):
        def commit(self) -> None:  # noqa: D102
            raise PersistenceFailure("intentional commit failure")

    # Each factory UoW owns a fresh connection; borrow one before it is entered.
    conn = uow_factory()._conn  # noqa: SLF001

    boom = BoomUow(conn, owns_connection=True)
    with pytest.raises(PersistenceFailure, match="intentional"):
        with boom:
            boom.evidence_items.save(e1)
            boom.evidence_snapshots.save(snap)
            boom.analysis_runs.save(run)
            boom.commit()

    with uow_factory() as uow:
        assert uow.evidence_items.get("ev_rb1") is None
        assert uow.evidence_snapshots.get("snap_rb") is None
        assert uow.analysis_runs.get("run_rb") is None
        uow.commit()


def test_migration_clean_db_applies_aquasignal(tmp_path: Path) -> None:
    files = list_migration_files()
    versions = [v for v, _ in files]
    assert 1 in versions
    assert 2 in versions

    db = tmp_path / "clean_a2.sqlite3"
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    newly = apply_migrations(conn)
    assert 1 in newly
    assert 2 in newly
    tables = {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    for name in (
        "observation_packets",
        "provenance_events",
        "evidence_items",
        "evidence_snapshots",
        "evidence_snapshot_members",
        "evidence_relations",
        "environmental_signals",
        "signal_evidence",
        "analysis_runs",
        "analysis_run_signals",
        "investigation_cases",
        "case_signals",
        "case_decisions",
        "human_decisions",
        "decision_signals",
    ):
        assert name in tables
    again = apply_migrations(conn)
    assert again == []
    conn.close()


@sqlite_only
def test_confirmgate_data_survives_aquasignal_migration(
    tmp_path: Path, coimbra, citizen: Actor
) -> None:
    """Apply only v1, insert a packet, then apply v2 — packet remains."""
    db = tmp_path / "cg_survive.sqlite3"
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    # Apply migration 1 only.
    from app.persistence.migrations_runner import MIGRATIONS_DIR, _utc_now_iso

    v1 = MIGRATIONS_DIR / "001_initial.sql"
    conn.executescript(v1.read_text(encoding="utf-8"))
    conn.execute(
        "INSERT INTO schema_migrations (version, applied_at, name) VALUES (?, ?, ?)",
        (1, _utc_now_iso(), v1.name),
    )
    conn.commit()

    settings = make_settings(db)
    # open_unit_of_work will apply pending v2 on prepare
    _conn, factory = open_unit_of_work(settings)
    svc = ObservationService(factory)
    packet = ObservationPacket.create(coimbra, author_actor_id=citizen.actor_id)
    packet.set_field(foam(), actor=citizen)
    svc.persist_new(packet)
    packet_id = packet.packet_id

    # Confirm AquaSignal tables exist and ConfirmGate row intact.
    tables = {
        r[0]
        for r in _conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert "evidence_items" in tables
    assert "observation_packets" in tables
    loaded = svc.get(packet_id)
    assert loaded.packet.fields["foam"].value == "present"
    events = svc.list_provenance(packet_id)
    assert any(e.action == "packet.created" for e in events)
    _conn.close()


def test_architecture_domain_still_free_of_persistence() -> None:
    import ast
    from pathlib import Path

    domain_root = Path(__file__).resolve().parents[3] / "app" / "domain"
    forbidden = {"sqlite3", "app.persistence"}
    for py in domain_root.rglob("*.py"):
        tree = ast.parse(py.read_text())
        names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    names.add(alias.name.split(".")[0])
                    parts = alias.name.split(".")
                    if parts[0] == "app" and len(parts) > 1:
                        names.add(f"app.{parts[1]}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                parts = node.module.split(".")
                names.add(parts[0])
                if parts[0] == "app" and len(parts) > 1:
                    names.add(f"app.{parts[1]}")
        bad = names & forbidden
        assert not bad, f"{py}: {bad}"
