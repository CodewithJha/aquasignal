"""ConfirmGate FINALIZED + labelled-fixture eligibility for AquaSignal evidence.

Domain/application gate — not UI. Detectors never enforce this.
"""

from __future__ import annotations

from datetime import datetime

from app.application.errors import EvidenceNotEligible
from app.domain.enums import WorkflowState
from app.domain.evidence.enums import EvidenceSourceClass
from app.domain.packet import ObservationPacket
from app.signals.models import EvidenceObservation


def require_finalized_packet(packet: ObservationPacket) -> None:
    """Refuse any non-FINALIZED ConfirmGate packet as investigation evidence."""
    if packet.workflow_state is not WorkflowState.FINALIZED:
        raise EvidenceNotEligible(
            f"ConfirmGate packet {packet.packet_id} is {packet.workflow_state.value}; "
            "only FINALIZED packets are eligible as ConfirmGate evidence",
            packet_id=packet.packet_id,
        )


def require_labelled_fixture(observation: EvidenceObservation) -> None:
    """Fixtures must be explicit synthetic + source_class=fixture."""
    if observation.source_class is not EvidenceSourceClass.FIXTURE:
        raise EvidenceNotEligible(
            f"fixture observation {observation.evidence_id} has source_class="
            f"{observation.source_class.value}; expected fixture"
        )
    if not observation.is_synthetic:
        raise EvidenceNotEligible(
            f"fixture observation {observation.evidence_id} must set is_synthetic=True"
        )


def observed_at_for_packet(packet: ObservationPacket) -> datetime:
    """Prefer effective_at; fall back to confirmation time (FINALIZED always has snapshot)."""
    if packet.effective_at is not None:
        return packet.effective_at
    if packet.confirmation is not None:
        return packet.confirmation.confirmed_at
    raise EvidenceNotEligible(
        f"FINALIZED packet {packet.packet_id} lacks effective_at and confirmation time",
        packet_id=packet.packet_id,
    )


def content_hash_for_packet(packet: ObservationPacket) -> str:
    if packet.confirmation is None:
        raise EvidenceNotEligible(
            f"FINALIZED packet {packet.packet_id} missing confirmation snapshot",
            packet_id=packet.packet_id,
        )
    return packet.confirmation.content_hash
