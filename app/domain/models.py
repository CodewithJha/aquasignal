"""Public domain surface + Phase 1 import compatibility.

Prefer importing from app.domain (package) or specific modules.
This module re-exports Phase 2 types so existing `from app.domain.models import …` keeps working.
"""

from __future__ import annotations

from app.domain.cities import OAH_CITIES
from app.domain.enums import (
    TERMINAL_STATES,
    ActorType,
    FieldSource,
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
from app.domain.provenance_port import (
    NullProvenanceSink,
    ProvenanceIntent,
    ProvenanceSink,
)
from app.domain.value_objects import (
    CITIZEN_SAFE_FIELD_CODES,
    EXCLUDED_FIELD_CODES,
    Actor,
    ConfirmationSnapshot,
    FieldValue,
    QualityFlag,
    SiteRef,
)

__all__ = [
    "OAH_CITIES",
    "TERMINAL_STATES",
    "LEGAL_TRANSITIONS",
    "ActorType",
    "FieldSource",
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
    "NullProvenanceSink",
    "ProvenanceIntent",
    "ProvenanceSink",
    "CITIZEN_SAFE_FIELD_CODES",
    "EXCLUDED_FIELD_CODES",
    "Actor",
    "ConfirmationSnapshot",
    "FieldValue",
    "QualityFlag",
    "SiteRef",
]
