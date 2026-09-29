"""EvidenceRelation — supports / conflicts / duplicates / insufficient link."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from app.domain.errors import DomainValidationError
from app.domain.evidence.enums import RelationType


@dataclass(frozen=True, slots=True)
class EvidenceRelation:
    """Explicit stance between two refs (evidence↔evidence or evidence↔signal)."""

    relation_id: str
    relation_type: RelationType
    left_ref: str
    right_ref: str
    analysis_run_id: str
    rationale_code: str
    message: str

    @classmethod
    def create(
        cls,
        *,
        relation_type: RelationType,
        left_ref: str,
        right_ref: str,
        analysis_run_id: str,
        rationale_code: str,
        message: str,
        relation_id: str | None = None,
    ) -> EvidenceRelation:
        if not left_ref.strip() or not right_ref.strip():
            raise DomainValidationError("left_ref and right_ref are required")
        if not analysis_run_id.strip():
            raise DomainValidationError("analysis_run_id is required")
        if not rationale_code.strip():
            raise DomainValidationError("rationale_code is required")
        return cls(
            relation_id=relation_id or f"rel_{uuid4().hex[:12]}",
            relation_type=relation_type,
            left_ref=left_ref.strip(),
            right_ref=right_ref.strip(),
            analysis_run_id=analysis_run_id.strip(),
            rationale_code=rationale_code.strip(),
            message=message.strip(),
        )
