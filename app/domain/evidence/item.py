"""EvidenceItem — normalized pointer to packet, fixture, or public series row."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping
from uuid import uuid4

from app.domain.errors import DomainValidationError
from app.domain.evidence.enums import EvidenceSourceClass
from app.domain.value_objects import SiteRef


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    """Immutable evidence pointer used in snapshots and relations.

    Fixtures must be explicitly labelled synthetic — never presented as live OAH data.
    ``fields`` holds protocol-lite string values for investigation display (not a
    free-form JSON blob in the brief layer).
    """

    evidence_id: str
    source_class: EvidenceSourceClass
    site: SiteRef
    observed_at: datetime
    payload_ref: str
    content_hash: str
    license_tag: str
    is_synthetic: bool
    fields: Mapping[str, str]

    @classmethod
    def create(
        cls,
        *,
        source_class: EvidenceSourceClass,
        site: SiteRef,
        observed_at: datetime,
        payload_ref: str,
        content_hash: str,
        license_tag: str,
        is_synthetic: bool,
        evidence_id: str | None = None,
        fields: Mapping[str, str] | None = None,
    ) -> EvidenceItem:
        if not payload_ref.strip():
            raise DomainValidationError("payload_ref is required")
        if not content_hash.strip():
            raise DomainValidationError("content_hash is required")
        if not license_tag.strip():
            raise DomainValidationError(
                "license_tag is required (especially for non-owned / public series)"
            )
        if source_class is EvidenceSourceClass.FIXTURE and not is_synthetic:
            raise DomainValidationError(
                "fixture evidence must be explicitly synthetic (is_synthetic=True)"
            )
        normalized = {
            str(k).strip(): str(v).strip()
            for k, v in dict(fields or {}).items()
            if str(k).strip()
        }
        return cls(
            evidence_id=evidence_id or f"ev_{uuid4().hex[:12]}",
            source_class=source_class,
            site=site,
            observed_at=observed_at,
            payload_ref=payload_ref.strip(),
            content_hash=content_hash.strip(),
            license_tag=license_tag.strip(),
            is_synthetic=is_synthetic,
            fields=normalized,
        )
