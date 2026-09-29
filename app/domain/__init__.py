"""ConfirmGate domain: ObservationPacket aggregate, workflow state machine, VOs."""

from app.domain.cities import OAH_CITIES
from app.domain.enums import (
    REJECTION_REASON_CODES,
    REJECTION_REASON_LABELS,
    TERMINAL_STATES,
    ActorType,
    FieldSource,
    RejectionReasonCode,
    Severity,
    WorkflowState,
)
from app.domain.errors import (
    ConfirmationBlocked,
    DomainValidationError,
    FinalizationBlocked,
    InvalidFieldValue,
    InvalidStateTransition,
    UnauthorizedDomainAction,
)
from app.domain.packet import LEGAL_TRANSITIONS, ObservationPacket, make_flag
from app.domain.provenance_port import ProvenanceIntent, ProvenanceSink
from app.domain.sites import SEED_SITES, get_site, list_sites
from app.domain.value_objects import (
    CITIZEN_SAFE_FIELD_CODES,
    Actor,
    ConfirmationSnapshot,
    FieldValue,
    QualityFlag,
    SiteRef,
)

__all__ = [
    "OAH_CITIES",
    "SEED_SITES",
    "get_site",
    "list_sites",
    "TERMINAL_STATES",
    "LEGAL_TRANSITIONS",
    "REJECTION_REASON_CODES",
    "REJECTION_REASON_LABELS",
    "ActorType",
    "FieldSource",
    "RejectionReasonCode",
    "Severity",
    "WorkflowState",
    "ConfirmationBlocked",
    "DomainValidationError",
    "FinalizationBlocked",
    "InvalidFieldValue",
    "InvalidStateTransition",
    "UnauthorizedDomainAction",
    "ObservationPacket",
    "make_flag",
    "ProvenanceIntent",
    "ProvenanceSink",
    "CITIZEN_SAFE_FIELD_CODES",
    "Actor",
    "ConfirmationSnapshot",
    "FieldValue",
    "QualityFlag",
    "SiteRef",
]
