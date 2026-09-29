"""Map ConfirmGate packets / fixtures → EvidenceObservation + EvidenceItem."""

from __future__ import annotations

from app.application.evidence_gate import (
    content_hash_for_packet,
    observed_at_for_packet,
    require_finalized_packet,
    require_labelled_fixture,
)
from app.domain.evidence.enums import EvidenceSourceClass
from app.domain.evidence.item import EvidenceItem
from app.domain.packet import ObservationPacket
from app.signals.models import EvidenceObservation

LICENSE_CONFIRMGATE = "confirmgate-demo"
LICENSE_FIXTURE = "fixture-owned-mit"


def packet_to_observation(packet: ObservationPacket) -> EvidenceObservation:
    """FINALIZED packet → pure EvidenceObservation for SignalEngine."""
    require_finalized_packet(packet)
    fields = {code: fv.value for code, fv in packet.fields.items()}
    return EvidenceObservation(
        evidence_id=packet.packet_id,
        site=packet.site,
        observed_at=observed_at_for_packet(packet),
        source_class=EvidenceSourceClass.CONFIRMGATE_PACKET,
        is_synthetic=False,
        fields=fields,
        payload_ref=f"packet:{packet.packet_id}",
        content_hash=content_hash_for_packet(packet),
        license_tag=LICENSE_CONFIRMGATE,
    )


def packet_to_evidence_item(packet: ObservationPacket) -> EvidenceItem:
    """FINALIZED packet → durable EvidenceItem (same id as observation)."""
    obs = packet_to_observation(packet)
    return EvidenceItem.create(
        evidence_id=obs.evidence_id,
        source_class=obs.source_class,
        site=obs.site,
        observed_at=obs.observed_at,
        payload_ref=obs.payload_ref,
        content_hash=obs.content_hash,
        license_tag=obs.license_tag,
        is_synthetic=obs.is_synthetic,
        fields=obs.fields,
    )


def fixture_to_evidence_item(observation: EvidenceObservation) -> EvidenceItem:
    """Labelled fixture observation → EvidenceItem."""
    require_labelled_fixture(observation)
    return EvidenceItem.create(
        evidence_id=observation.evidence_id,
        source_class=EvidenceSourceClass.FIXTURE,
        site=observation.site,
        observed_at=observation.observed_at,
        payload_ref=observation.payload_ref or f"fixture:{observation.evidence_id}",
        content_hash=observation.content_hash or f"fixture-hash-{observation.evidence_id}",
        license_tag=observation.license_tag or LICENSE_FIXTURE,
        is_synthetic=True,
        fields=observation.fields,
    )
