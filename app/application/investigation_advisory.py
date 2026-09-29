"""Build InvestigationBriefInput + soft-call InvestigationCopilotPort."""

from __future__ import annotations

import logging
from typing import Any

from app.ai.errors import AiAssistTimeout, AiAssistUnavailable
from app.ai.investigation_port import (
    AdvisoryBrief,
    CopilotEvidenceRef,
    CopilotSignalRef,
    InvestigationBriefInput,
    InvestigationCopilotPort,
)
from app.ai.investigation_validate import hash_investigation_brief
from app.ai.prompts import INVESTIGATION_COPILOT_PROMPT_VERSION
from app.application.investigation_brief import AnalysisBrief

logger = logging.getLogger("aquasignal.investigation_advisory")


def brief_to_copilot_input(brief: AnalysisBrief) -> InvestigationBriefInput:
    """Deterministic immutable subset — no repos / detectors / network."""
    return InvestigationBriefInput(
        run_id=brief.run_id,
        site_id=brief.site_id,
        site_label=brief.site_label,
        status=brief.status,
        detector_set_version=brief.detector_set_version,
        evidence_count=brief.evidence_count,
        signal_count=brief.signal_count,
        supporting=brief.stance.supporting,
        conflicting=brief.stance.conflicting,
        insufficient=brief.stance.insufficient,
        duplicates=brief.stance.duplicates,
        no_signal_success=brief.no_signal_success,
        failed=brief.failed,
        signals=tuple(
            CopilotSignalRef(
                signal_id=s.signal_id,
                signal_type=s.signal_type,
                summary=s.summary,
                is_insufficient=s.is_insufficient,
                evidence_ids=s.evidence_ids,
            )
            for s in brief.signals
        ),
        evidence=tuple(
            CopilotEvidenceRef(
                evidence_id=e.evidence_id,
                source_class=e.source_class,
                is_synthetic=e.is_synthetic,
                fields=dict(e.fields),
            )
            for e in brief.evidence
        ),
        contradiction_messages=tuple(c.message for c in brief.contradictions),
        supports_messages=brief.supports_messages,
        system_analysis_note=brief.system_analysis_note,
    )


def safe_advise(
    copilot: InvestigationCopilotPort,
    brief: AnalysisBrief,
) -> AdvisoryBrief:
    """Call copilot; never raise into the investigation page / analysis path."""
    inp = brief_to_copilot_input(brief)
    brief_hash = hash_investigation_brief(inp)
    try:
        advisory = copilot.advise(inp)
    except AiAssistTimeout:
        logger.warning(
            "investigation.advisory.timeout",
            extra={
                "run_id": brief.run_id,
                "input_brief_hash": brief_hash,
                "provider": getattr(copilot, "provider_name", None),
                "model": getattr(copilot, "model_id", None),
                "prompt_version": INVESTIGATION_COPILOT_PROMPT_VERSION,
            },
        )
        return AdvisoryBrief(
            provider=getattr(copilot, "provider_name", "unknown"),
            model=getattr(copilot, "model_id", "unknown"),
            prompt_version=INVESTIGATION_COPILOT_PROMPT_VERSION,
            input_brief_hash=brief_hash,
            validation_status="timeout",
            available=False,
            notes="Investigation advisory timed out.",
        )
    except (AiAssistUnavailable, Exception) as exc:
        logger.warning(
            "investigation.advisory.unavailable",
            extra={
                "run_id": brief.run_id,
                "input_brief_hash": brief_hash,
                "error": type(exc).__name__,
                "provider": getattr(copilot, "provider_name", None),
                "model": getattr(copilot, "model_id", None),
            },
        )
        return AdvisoryBrief(
            provider=getattr(copilot, "provider_name", "unknown"),
            model=getattr(copilot, "model_id", "unknown"),
            prompt_version=INVESTIGATION_COPILOT_PROMPT_VERSION,
            input_brief_hash=brief_hash,
            validation_status="unavailable",
            available=False,
            notes="Investigation advisory unavailable.",
        )
    return advisory


def advisory_to_api(advisory: AdvisoryBrief) -> dict[str, Any]:
    return {
        "available": advisory.available,
        "validation_status": advisory.validation_status,
        "summary": advisory.summary,
        "signal_explanations": [
            {"signal_id": s.signal_id, "explanation": s.explanation}
            for s in advisory.signal_explanations
        ],
        "missing_evidence": list(advisory.missing_evidence),
        "limitations": list(advisory.limitations),
        "provenance": {
            "provider": advisory.provider,
            "model": advisory.model,
            "prompt_version": advisory.prompt_version,
            "input_brief_hash": advisory.input_brief_hash,
            "validation_status": advisory.validation_status,
        },
        "notes": advisory.notes,
    }
