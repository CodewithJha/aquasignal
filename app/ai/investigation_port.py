"""InvestigationCopilotPort — optional advisory over a frozen investigation brief.

AI never mutates signals, evidence, runs, cases, decisions, packets, or FHIR.
Null-first; failures are soft.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping, Protocol, Sequence

from pydantic import BaseModel, Field, field_validator

MissingEvidenceCode = Literal[
    "additional_observation",
    "longer_time_window",
    "repeat_protocol_observation",
    "human_review",
]

MISSING_EVIDENCE_VOCAB: frozenset[str] = frozenset(
    {
        "additional_observation",
        "longer_time_window",
        "repeat_protocol_observation",
        "human_review",
    }
)

ValidationStatus = Literal["valid", "rejected", "unavailable", "timeout", "null"]


@dataclass(frozen=True, slots=True)
class CopilotSignalRef:
    """Deterministic signal slice for the copilot — ids must exist on the brief."""

    signal_id: str
    signal_type: str
    summary: str
    is_insufficient: bool
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CopilotEvidenceRef:
    evidence_id: str
    source_class: str
    is_synthetic: bool
    fields: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class InvestigationBriefInput:
    """Immutable deterministic subset passed to InvestigationCopilotPort.

    No DB handles, repos, detectors, or network. Built from AnalysisBrief only.
    """

    run_id: str
    site_id: str
    site_label: str
    status: str
    detector_set_version: str
    evidence_count: int
    signal_count: int
    supporting: int
    conflicting: int
    insufficient: int
    duplicates: int
    no_signal_success: bool
    failed: bool
    signals: tuple[CopilotSignalRef, ...]
    evidence: tuple[CopilotEvidenceRef, ...]
    contradiction_messages: tuple[str, ...]
    supports_messages: tuple[str, ...]
    system_analysis_note: str

    @property
    def known_signal_ids(self) -> frozenset[str]:
        return frozenset(s.signal_id for s in self.signals)

    @property
    def known_evidence_ids(self) -> frozenset[str]:
        return frozenset(e.evidence_id for e in self.evidence)


class SignalExplanationItem(BaseModel):
    signal_id: str
    explanation: str

    @field_validator("signal_id", "explanation", mode="before")
    @classmethod
    def _strip(cls, v: object) -> str:
        text = str(v).strip() if v is not None else ""
        if not text:
            raise ValueError("signal_id and explanation must be non-empty")
        return text


class AdvisoryBrief(BaseModel):
    """Schema-validated AI advisory — never authoritative."""

    summary: str = ""
    signal_explanations: list[SignalExplanationItem] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    provider: str = "null"
    model: str = "null"
    prompt_version: str | None = None
    input_brief_hash: str = ""
    validation_status: ValidationStatus = "null"
    available: bool = False
    notes: str | None = None

    @field_validator("missing_evidence", mode="before")
    @classmethod
    def _list_str(cls, v: object) -> list[str]:
        if v is None:
            return []
        if not isinstance(v, Sequence) or isinstance(v, (str, bytes)):
            raise ValueError("missing_evidence must be a list")
        return [str(x).strip() for x in v if str(x).strip()]

    @field_validator("limitations", mode="before")
    @classmethod
    def _lim(cls, v: object) -> list[str]:
        if v is None:
            return []
        if not isinstance(v, Sequence) or isinstance(v, (str, bytes)):
            raise ValueError("limitations must be a list")
        return [str(x).strip() for x in v if str(x).strip()]


class InvestigationCopilotPort(Protocol):
    """Replaceable investigation advisory. Implementations must not write domain/DB."""

    model_id: str
    provider_name: str

    def advise(self, brief: InvestigationBriefInput) -> AdvisoryBrief:
        ...
