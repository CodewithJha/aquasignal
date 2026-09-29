"""HITL audit answers derived from durable provenance (PROV-002)."""

from __future__ import annotations

from typing import Any

from app.application.ports import ProvenanceRecord


def answer_hitl_audit_questions(
    events: list[ProvenanceRecord],
) -> dict[str, Any]:
    """Answer spike Part 8 questions from append-only provenance alone.

    Missing facets are explicitly ``"N/A"`` (e.g. no AI → Q2).
    Bundle hash (Q6) and mapper version (Q7) come from ``fhir.exported``
    and/or ``fhir.export_digest`` (Phase 5).
    """
    created = next((e for e in events if e.action == "packet.created"), None)
    field_sets = [e for e in events if e.action in {"fields.set", "fields.replaced"}]
    suggestions = [e for e in events if e.action == "suggestions.applied"]
    flags_raised = [e for e in events if e.action == "flags.raised"]
    overrides = [e for e in events if e.action == "flag.overridden"]
    confirmed = next(
        (
            e
            for e in events
            if e.action in {"human.confirmed", "review.accepted"}
        ),
        None,
    )
    exported = next((e for e in events if e.action == "fhir.exported"), None)
    digest = next((e for e in events if e.action == "fhir.export_digest"), None)

    q1 = {
        "event": created.to_audit_dict() if created else None,
        "initial_field_events": [e.to_audit_dict() for e in field_sets[:1]],
        "summary": "N/A" if not created else "see packet.created + early fields.*",
    }
    if suggestions:
        q2 = [
            {
                "model_id": e.model_id,
                "prompt_version": e.prompt_version,
                "at": e.at.isoformat(),
                "suggestions": (e.after or {}).get("suggestions"),
            }
            for e in suggestions
        ]
    else:
        q2 = "N/A"

    q3 = {
        "field_mutations": [e.to_audit_dict() for e in field_sets],
        "note": (
            "Human accept without edit is evidenced by confirm hash matching "
            "fields without intervening fields.* after suggestions"
        ),
    }
    q4 = {
        "raised": [e.to_audit_dict() for e in flags_raised],
        "overridden": [e.to_audit_dict() for e in overrides],
    }
    q5 = confirmed.to_audit_dict() if confirmed else "N/A"

    export_after: dict[str, Any] = {}
    if exported and exported.after:
        export_after.update(exported.after)
    if digest and digest.after:
        export_after.update(digest.after)

    if export_after.get("confirmation_hash") or export_after.get("bundle_hash"):
        q6 = {
            "confirmation_hash": export_after.get("confirmation_hash", "N/A"),
            "fhir_bundle_id": export_after.get("fhir_bundle_id"),
            "bundle_bytes_hash": export_after.get("bundle_hash", "N/A"),
        }
    else:
        q6 = "N/A"

    mapper_version = export_after.get("mapper_version", "N/A")
    if exported or digest:
        q7 = {
            "rule_engine_version": (
                (digest.rule_engine_version if digest else None)
                or (exported.rule_engine_version if exported else None)
                or "N/A"
            ),
            "mapper_version": mapper_version,
        }
    else:
        last_flags = flags_raised[-1] if flags_raised else None
        q7 = {
            "rule_engine_version": (
                last_flags.rule_engine_version if last_flags else "N/A"
            ),
            "mapper_version": "N/A",
        }

    return {
        "1_citizen_initial_submit": q1,
        "2_ai_suggestions": q2,
        "3_human_change_vs_accept": q3,
        "4_flags_raised_overridden": q4,
        "5_who_confirmed_when": q5,
        "6_exported_bundle_hash": q6,
        "7_rule_and_mapper_versions": q7,
        "_event_count": len(events),
        "_actions": [e.action for e in events],
    }
