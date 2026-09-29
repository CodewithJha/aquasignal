"""Versioned AI prompts — never embedded in routes, templates, or domain."""

from __future__ import annotations

from typing import Any

# Bump when prompt text or output contract changes (recorded in provenance).
PROMPT_VERSION = "enum-suggest-v1"
FLAG_EXPLAIN_PROMPT_VERSION = "flag-explain-v1"
INVESTIGATION_COPILOT_PROMPT_VERSION = "investigation_copilot_v1"

ENUM_SUGGEST_SYSTEM = """You assist ConfirmGate with OPTIONAL categorical suggestions only.
Return JSON object: {"suggestions":[{"field":"<code>","suggested_value":"<value>","explanation":"<short>"}]}.
Rules:
- Suggest ONLY for empty protocol-lite fields from the allowlist.
- suggested_value MUST be from the provided vocabulary for that field.
- Do NOT invent ecological health indices (BMWP, IBD, EFI), pathogens, disease,
  outbreak, AMR, pharmaceuticals, lab results, water-safety diagnosis, or trust scores.
- Do NOT decide valid/invalid, confirm, finalize, or generate FHIR/OAH codes.
- Keep explanations short and advisory. Human review is mandatory.
"""

FLAG_EXPLAIN_SYSTEM = """You rephrase an existing deterministic quality-flag message for a citizen.
Return JSON: {"explanation":"<plain language>"}.
Rules:
- Ground the explanation in the provided flag message only.
- Do NOT change severity, code, rule_id, or blocking behavior.
- Do NOT invent new findings, health diagnoses, or ecological scores.
"""

INVESTIGATION_COPILOT_SYSTEM = """You are an OPTIONAL Investigation Copilot for AquaSignal.
Return JSON only:
{
  "summary": "<short non-diagnostic restatement of the investigation brief>",
  "signal_explanations": [{"signal_id":"<existing id>","explanation":"<plain language>"}],
  "missing_evidence": ["<closed vocab only>"],
  "limitations": ["<honest limit of this brief>"]
}

Closed missing_evidence vocabulary (only these strings):
- additional_observation
- longer_time_window
- repeat_protocol_observation
- human_review

HARD RULES (non-diagnostic):
- Explain ONLY deterministic signals / stance already present in the input.
- signal_id MUST be an id listed in the input. Never invent signal or evidence ids.
- Do NOT claim pollution, contamination, disease, pathogen, AMR, outbreak, health risk,
  causality, water safety, alerts, confidence scores, or trust scores.
- Do NOT mutate or invent analysis results. AI is never authority.
- Prefer saying evidence is insufficient over speculative conclusions.
- Human review remains required for any InvestigationCase decision.
"""


def build_enum_suggest_user_payload(
    *,
    fields: dict[str, Any],
    empty_fields: list[str],
    vocabularies: dict[str, list[str]],
) -> dict[str, Any]:
    return {
        "purpose": "enum_suggestion",
        "prompt_version": PROMPT_VERSION,
        "current_fields": fields,
        "empty_fields": empty_fields,
        "vocabularies": vocabularies,
        "instruction": "Suggest values only for empty_fields using vocabularies.",
    }


def build_flag_explain_user_payload(
    *,
    flag_id: str,
    rule_id: str,
    code: str,
    severity: str,
    message: str,
) -> dict[str, Any]:
    return {
        "purpose": "flag_explain",
        "prompt_version": FLAG_EXPLAIN_PROMPT_VERSION,
        "flag_id": flag_id,
        "rule_id": rule_id,
        "code": code,
        "severity": severity,
        "message": message,
        "instruction": "Rephrase message only; do not alter severity or code.",
    }


def build_investigation_copilot_user_payload(
    *,
    brief_hash: str,
    bounded: dict[str, Any],
) -> dict[str, Any]:
    return {
        "purpose": "investigation_advisory",
        "prompt_version": INVESTIGATION_COPILOT_PROMPT_VERSION,
        "input_brief_hash": brief_hash,
        "brief": bounded,
        "instruction": (
            "Summarize and explain only what is in brief. "
            "Use existing signal ids only. No diagnostic claims."
        ),
    }
