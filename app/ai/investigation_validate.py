"""Validate Investigation Copilot AdvisoryBrief against closed vocab + brief ids."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from app.ai.claim_safety import contains_forbidden_claim, unknown_id_references
from app.ai.investigation_port import (
    MISSING_EVIDENCE_VOCAB,
    AdvisoryBrief,
    InvestigationBriefInput,
    SignalExplanationItem,
)
from app.ai.prompts import INVESTIGATION_COPILOT_PROMPT_VERSION


def hash_investigation_brief(brief: InvestigationBriefInput) -> str:
    """Stable SHA-256 of the bounded copilot input (no secrets / full prompts)."""
    payload = bounded_brief_for_prompt(brief)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def bounded_brief_for_prompt(brief: InvestigationBriefInput) -> dict[str, Any]:
    """Compact AI input — counts, ids, summaries only; no raw detector internals."""
    return {
        "run_id": brief.run_id,
        "site_id": brief.site_id,
        "site_label": brief.site_label,
        "status": brief.status,
        "detector_set_version": brief.detector_set_version,
        "counts": {
            "evidence": brief.evidence_count,
            "signals": brief.signal_count,
            "supporting": brief.supporting,
            "conflicting": brief.conflicting,
            "insufficient": brief.insufficient,
            "duplicates": brief.duplicates,
        },
        "no_signal_success": brief.no_signal_success,
        "failed": brief.failed,
        "signals": [
            {
                "signal_id": s.signal_id,
                "signal_type": s.signal_type,
                "summary": s.summary,
                "is_insufficient": s.is_insufficient,
                "evidence_ids": list(s.evidence_ids),
            }
            for s in brief.signals
        ],
        "evidence": [
            {
                "evidence_id": e.evidence_id,
                "source_class": e.source_class,
                "is_synthetic": e.is_synthetic,
                "fields": dict(e.fields),
            }
            for e in brief.evidence
        ],
        "contradiction_messages": list(brief.contradiction_messages),
        "supports_messages": list(brief.supports_messages),
        "system_analysis_note": brief.system_analysis_note,
        "missing_evidence_vocab": sorted(MISSING_EVIDENCE_VOCAB),
    }


def validate_advisory_brief(
    raw: Mapping[str, Any] | AdvisoryBrief | None,
    *,
    brief: InvestigationBriefInput,
    provider: str,
    model: str,
    prompt_version: str | None = None,
    input_brief_hash: str | None = None,
) -> AdvisoryBrief:
    """Return a typed AdvisoryBrief. Reject invent ids / forbidden claims / bad vocab.

    On rejection returns available=False with validation_status='rejected' (never raises
    into analysis). Schema-malformed input also rejected.
    """
    brief_hash = input_brief_hash or hash_investigation_brief(brief)
    version = prompt_version or INVESTIGATION_COPILOT_PROMPT_VERSION
    empty = AdvisoryBrief(
        summary="",
        signal_explanations=[],
        missing_evidence=[],
        limitations=[],
        provider=provider,
        model=model,
        prompt_version=version,
        input_brief_hash=brief_hash,
        validation_status="rejected",
        available=False,
        notes="Advisory rejected by schema / scientific-boundary validation.",
    )
    if raw is None:
        return empty
    try:
        if isinstance(raw, AdvisoryBrief):
            candidate = raw
        else:
            candidate = AdvisoryBrief.model_validate(
                {
                    "summary": raw.get("summary", ""),
                    "signal_explanations": raw.get("signal_explanations") or [],
                    "missing_evidence": raw.get("missing_evidence") or [],
                    "limitations": raw.get("limitations") or [],
                    "provider": provider,
                    "model": model,
                    "prompt_version": version,
                    "input_brief_hash": brief_hash,
                    "validation_status": "valid",
                    "available": True,
                    "notes": raw.get("notes"),
                }
            )
    except Exception:
        return empty.model_copy(
            update={"notes": "Advisory rejected: malformed JSON / schema."}
        )

    echoed_hash = None if isinstance(raw, AdvisoryBrief) else raw.get("input_brief_hash")
    if echoed_hash is not None and echoed_hash != brief_hash:
        return empty.model_copy(
            update={"notes": "Advisory rejected: input_brief_hash does not match the brief."}
        )

    texts = [candidate.summary, *candidate.limitations]
    for item in candidate.signal_explanations:
        texts.append(item.explanation)
    if any(contains_forbidden_claim(t) for t in texts):
        return empty.model_copy(
            update={"notes": "Advisory rejected: forbidden scientific / risk claim."}
        )

    known_ids = brief.known_signal_ids | brief.known_evidence_ids | {brief.run_id}
    unknown = set().union(*(unknown_id_references(t, known_ids) for t in texts))
    if unknown:
        return empty.model_copy(
            update={
                "notes": f"Advisory rejected: references unknown ids {sorted(unknown)!r}."
            }
        )

    known_signals = brief.known_signal_ids
    explanations: list[SignalExplanationItem] = []
    seen: set[str] = set()
    for item in candidate.signal_explanations:
        if item.signal_id not in known_signals:
            return empty.model_copy(
                update={
                    "notes": (
                        f"Advisory rejected: unknown signal_id {item.signal_id!r}."
                    )
                }
            )
        if item.signal_id in seen:
            continue
        seen.add(item.signal_id)
        explanations.append(item)

    missing: list[str] = []
    for code in candidate.missing_evidence:
        if code not in MISSING_EVIDENCE_VOCAB:
            return empty.model_copy(
                update={
                    "notes": (
                        f"Advisory rejected: invalid missing_evidence {code!r}."
                    )
                }
            )
        if code not in missing:
            missing.append(code)

    summary = candidate.summary.strip()
    if not summary and not explanations and not missing and not candidate.limitations:
        return empty.model_copy(
            update={
                "validation_status": "rejected",
                "notes": "Advisory rejected: empty advisory body.",
                "available": False,
            }
        )

    return AdvisoryBrief(
        summary=summary,
        signal_explanations=explanations,
        missing_evidence=missing,
        limitations=list(candidate.limitations),
        provider=provider,
        model=model,
        prompt_version=version,
        input_brief_hash=brief_hash,
        validation_status="valid",
        available=True,
        notes=candidate.notes,
    )
