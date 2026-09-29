"""AquaSignal A2 — evidence item / snapshot / relation repository tests."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.application.errors import ForeignKeyViolation, ResourceNotFound
from app.domain.errors import DomainValidationError
from app.domain.evidence.enums import EvidenceSourceClass
from app.domain.evidence.item import EvidenceItem
from app.domain.evidence.snapshot import EvidenceSnapshot, compute_snapshot_hash
from tests.persistence.aquasignal.conftest import (
    make_fixture_evidence,
    make_packet_evidence,
    make_relation,
    make_run,
    make_snapshot,
)


def test_evidence_item_crud_and_not_found(uow_factory, coimbra, observed_at) -> None:
    item = make_packet_evidence(coimbra, observed_at, eid="ev_packet_1")
    with uow_factory() as uow:
        saved = uow.evidence_items.save(item)
        uow.commit()
    assert saved.evidence_id == "ev_packet_1"
    assert saved.is_synthetic is False

    with uow_factory() as uow:
        loaded = uow.evidence_items.require("ev_packet_1")
        assert loaded.payload_ref == "packet:ev_packet_1"
        assert loaded.site.city == "Coimbra"
        with pytest.raises(ResourceNotFound):
            uow.evidence_items.require("missing")
        uow.commit()


def test_fixture_synthetic_enforced_on_save_and_load(
    uow_factory, coimbra, observed_at
) -> None:
    fixture = make_fixture_evidence(coimbra, observed_at, eid="ev_fix_1")
    with uow_factory() as uow:
        uow.evidence_items.save(fixture)
        uow.commit()

    with uow_factory() as uow:
        loaded = uow.evidence_items.require("ev_fix_1")
        assert loaded.source_class is EvidenceSourceClass.FIXTURE
        assert loaded.is_synthetic is True
        uow.commit()

    with pytest.raises(DomainValidationError):
        EvidenceItem.create(
            source_class=EvidenceSourceClass.FIXTURE,
            site=coimbra,
            observed_at=observed_at,
            payload_ref="bad",
            content_hash="h",
            license_tag="x",
            is_synthetic=False,
        )


def test_snapshot_hash_and_order_round_trip(uow_factory, coimbra, observed_at) -> None:
    e1 = make_packet_evidence(coimbra, observed_at, eid="ev_a")
    e2 = make_fixture_evidence(coimbra, observed_at, eid="ev_b")
    e3 = make_packet_evidence(
        coimbra,
        datetime(2026, 9, 11, tzinfo=timezone.utc),
        eid="ev_c",
    )
    ordered = ("ev_c", "ev_a", "ev_b")  # deliberate non-alpha order
    snap = make_snapshot(ordered, sid="snap_order")

    with uow_factory() as uow:
        for item in (e1, e2, e3):
            uow.evidence_items.save(item)
        saved = uow.evidence_snapshots.save(snap)
        uow.commit()

    assert saved.ordered_evidence_ids == ordered
    assert saved.snapshot_hash == compute_snapshot_hash(
        ordered, {"source": "a2-test", "n": 3}
    )

    with uow_factory() as uow:
        loaded = uow.evidence_snapshots.require("snap_order")
        assert loaded.ordered_evidence_ids == ordered
        assert loaded.snapshot_hash == snap.snapshot_hash
        assert dict(loaded.source_manifest) == {"n": 3, "source": "a2-test"}
        uow.commit()


def test_snapshot_fk_requires_evidence(uow_factory) -> None:
    snap = EvidenceSnapshot.create(
        snapshot_id="snap_orphan",
        ordered_evidence_ids=("ev_missing",),
        source_manifest={},
    )
    with uow_factory() as uow:
        with pytest.raises(ForeignKeyViolation):
            uow.evidence_snapshots.save(snap)
        uow.rollback()


def test_relation_fk_requires_run(uow_factory, coimbra, observed_at) -> None:
    rel = make_relation(run_id="run_missing", left="ev_a", right="ev_b")
    with uow_factory() as uow:
        with pytest.raises(ForeignKeyViolation):
            uow.evidence_relations.save(rel)
        uow.rollback()


def test_relation_crud_with_run(uow_factory, coimbra, observed_at) -> None:
    e1 = make_packet_evidence(coimbra, observed_at, eid="ev_r1")
    e2 = make_packet_evidence(coimbra, observed_at, eid="ev_r2")
    snap = make_snapshot(("ev_r1", "ev_r2"), sid="snap_rel")
    run = make_run(snapshot_hash=snap.snapshot_hash, run_id="run_rel")
    rel = make_relation(run_id=run.run_id, left="ev_r1", right="ev_r2", rid="rel_1")

    with uow_factory() as uow:
        uow.evidence_items.save(e1)
        uow.evidence_items.save(e2)
        uow.evidence_snapshots.save(snap)
        uow.analysis_runs.save(run)
        saved = uow.evidence_relations.save(rel)
        uow.commit()

    assert saved.rationale_code == "protocol_conflict"

    with uow_factory() as uow:
        loaded = uow.evidence_relations.require("rel_1")
        assert loaded.left_ref == "ev_r1"
        listed = uow.evidence_relations.list_for_run(run.run_id)
        assert [r.relation_id for r in listed] == ["rel_1"]
        with pytest.raises(ResourceNotFound):
            uow.evidence_relations.require("rel_missing")
        uow.commit()
