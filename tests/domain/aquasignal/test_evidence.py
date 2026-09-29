"""EvidenceItem + EvidenceRelation creation and fixture synthetic invariant."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.domain.errors import DomainValidationError
from app.domain.evidence.enums import EvidenceSourceClass, RelationType
from app.domain.evidence.item import EvidenceItem
from app.domain.evidence.relation import EvidenceRelation
from app.domain.value_objects import SiteRef


def test_create_confirmgate_packet_evidence(coimbra_site: SiteRef) -> None:
    item = EvidenceItem.create(
        source_class=EvidenceSourceClass.CONFIRMGATE_PACKET,
        site=coimbra_site,
        observed_at=datetime(2026, 9, 10, tzinfo=timezone.utc),
        payload_ref="pkt_abc",
        content_hash="a" * 64,
        license_tag="owned",
        is_synthetic=False,
    )
    assert item.source_class is EvidenceSourceClass.CONFIRMGATE_PACKET
    assert item.site.site_id == "coimbra"
    assert item.is_synthetic is False
    assert item.evidence_id


def test_fixture_must_be_explicitly_synthetic(coimbra_site: SiteRef) -> None:
    with pytest.raises(DomainValidationError, match="synthetic"):
        EvidenceItem.create(
            source_class=EvidenceSourceClass.FIXTURE,
            site=coimbra_site,
            observed_at=datetime(2026, 9, 10, tzinfo=timezone.utc),
            payload_ref="fix_row_1",
            content_hash="b" * 64,
            license_tag="MIT-demo",
            is_synthetic=False,
        )


def test_fixture_with_synthetic_ok(coimbra_site: SiteRef) -> None:
    item = EvidenceItem.create(
        source_class=EvidenceSourceClass.FIXTURE,
        site=coimbra_site,
        observed_at=datetime(2026, 9, 10, tzinfo=timezone.utc),
        payload_ref="fix_row_1",
        content_hash="b" * 64,
        license_tag="synthetic-demo",
        is_synthetic=True,
    )
    assert item.is_synthetic is True
    assert item.source_class is EvidenceSourceClass.FIXTURE


def test_public_series_requires_license_tag(coimbra_site: SiteRef) -> None:
    with pytest.raises(DomainValidationError, match="license"):
        EvidenceItem.create(
            source_class=EvidenceSourceClass.PUBLIC_SERIES,
            site=coimbra_site,
            observed_at=datetime(2026, 9, 10, tzinfo=timezone.utc),
            payload_ref="eea-series-1",
            content_hash="c" * 64,
            license_tag="",
            is_synthetic=False,
        )


def test_evidence_relation_types() -> None:
    for rel in (
        RelationType.SUPPORTS,
        RelationType.CONFLICTS,
        RelationType.DUPLICATES,
        RelationType.INSUFFICIENT,
    ):
        relation = EvidenceRelation.create(
            relation_type=rel,
            left_ref="ev_1",
            right_ref="ev_2",
            analysis_run_id="run_1",
            rationale_code="field_diff",
            message="foam disagree",
        )
        assert relation.relation_type is rel
        assert relation.relation_id
