"""EvidenceSnapshot deterministic hash contract."""

from __future__ import annotations

from datetime import datetime, timezone

from app.domain.evidence.snapshot import EvidenceSnapshot


def test_snapshot_hash_deterministic() -> None:
    created = datetime(2026, 9, 22, 8, 0, tzinfo=timezone.utc)
    a = EvidenceSnapshot.create(
        ordered_evidence_ids=("ev_a", "ev_b", "ev_c"),
        source_manifest={"fixture": 2, "confirmgate_packet": 1},
        created_at=created,
    )
    b = EvidenceSnapshot.create(
        ordered_evidence_ids=("ev_a", "ev_b", "ev_c"),
        source_manifest={"confirmgate_packet": 1, "fixture": 2},
        created_at=created,
    )
    assert a.snapshot_hash == b.snapshot_hash
    assert a.snapshot_hash
    assert len(a.snapshot_hash) == 64


def test_snapshot_hash_order_sensitive() -> None:
    created = datetime(2026, 9, 22, 8, 0, tzinfo=timezone.utc)
    a = EvidenceSnapshot.create(
        ordered_evidence_ids=("ev_a", "ev_b"),
        source_manifest={},
        created_at=created,
    )
    b = EvidenceSnapshot.create(
        ordered_evidence_ids=("ev_b", "ev_a"),
        source_manifest={},
        created_at=created,
    )
    assert a.snapshot_hash != b.snapshot_hash


def test_snapshot_ref_matches_hash() -> None:
    snap = EvidenceSnapshot.create(
        ordered_evidence_ids=("ev_1",),
        source_manifest={"fixture": 1},
    )
    ref = snap.as_ref()
    assert ref.snapshot_id == snap.snapshot_id
    assert ref.snapshot_hash == snap.snapshot_hash
