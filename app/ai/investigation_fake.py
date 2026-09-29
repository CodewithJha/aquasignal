"""Fake Investigation Copilot — offline deterministic advisories for tests."""

from __future__ import annotations

from typing import Any, Callable, Mapping

from app.ai.errors import AiAssistTimeout, AiAssistUnavailable
from app.ai.investigation_port import AdvisoryBrief, InvestigationBriefInput
from app.ai.investigation_validate import (
    hash_investigation_brief,
    validate_advisory_brief,
)
from app.ai.prompts import INVESTIGATION_COPILOT_PROMPT_VERSION

PayloadFactory = Callable[[InvestigationBriefInput], Mapping[str, Any] | None]


class FakeInvestigationCopilot:
    """Deterministic offline copilot. Selected via AI_PROVIDER=fake or tests."""

    model_id: str = "fake-investigation-v1"
    provider_name: str = "fake"

    def __init__(
        self,
        *,
        mode: str = "valid",
        payload: Mapping[str, Any] | None = None,
        payload_factory: PayloadFactory | None = None,
    ) -> None:
        self._mode = mode
        self._payload = dict(payload) if payload else None
        self._payload_factory = payload_factory

    def advise(self, brief: InvestigationBriefInput) -> AdvisoryBrief:
        brief_hash = hash_investigation_brief(brief)
        if self._mode == "timeout":
            raise AiAssistTimeout("fake investigation timeout")
        if self._mode == "unavailable":
            raise AiAssistUnavailable("fake investigation unavailable")
        if self._mode == "malformed":
            # Bypass pydantic path via validate with garbage string-shaped dict
            return validate_advisory_brief(
                {"summary": 123, "signal_explanations": "not-a-list"},
                brief=brief,
                provider=self.provider_name,
                model=self.model_id,
                prompt_version=INVESTIGATION_COPILOT_PROMPT_VERSION,
                input_brief_hash=brief_hash,
            )

        if self._payload_factory is not None:
            raw = self._payload_factory(brief)
        elif self._payload is not None:
            raw = self._payload
        else:
            raw = self._default_payload(brief)

        if self._mode == "invalid_signal_id":
            raw = {
                **dict(raw or {}),
                "signal_explanations": [
                    {
                        "signal_id": "sig_does_not_exist",
                        "explanation": "Invented signal explanation.",
                    }
                ],
            }
        elif self._mode == "invalid_missing":
            raw = {
                **dict(raw or {}),
                "missing_evidence": ["lab_pathogen_panel"],
            }
        elif self._mode == "forbidden":
            raw = {
                "summary": "Pollution detected; high health risk from pathogens.",
                "signal_explanations": [],
                "missing_evidence": [],
                "limitations": [],
            }

        return validate_advisory_brief(
            raw,
            brief=brief,
            provider=self.provider_name,
            model=self.model_id,
            prompt_version=INVESTIGATION_COPILOT_PROMPT_VERSION,
            input_brief_hash=brief_hash,
        )

    def _default_payload(self, brief: InvestigationBriefInput) -> dict[str, Any]:
        explanations = []
        for sig in brief.signals[:5]:
            explanations.append(
                {
                    "signal_id": sig.signal_id,
                    "explanation": (
                        f"Offline restatement of deterministic signal "
                        f"{sig.signal_type}: {sig.summary} "
                        "This is advisory only — not authority."
                    ),
                }
            )
        missing: list[str] = []
        if brief.insufficient or brief.failed or brief.signal_count == 0:
            missing.append("additional_observation")
        if brief.conflicting:
            missing.append("human_review")
        limitations = [
            "Advisory restates SYSTEM ANALYSIS only; AI is not authority.",
            "Synthetic fixtures are labelled and not live OneAquaHealth feeds.",
        ]
        summary = (
            f"Investigation brief for {brief.site_label} has "
            f"{brief.signal_count} signal(s) and {brief.evidence_count} evidence item(s). "
            "Restates SYSTEM ANALYSIS only; not a diagnostic conclusion."
        )
        return {
            "summary": summary,
            "signal_explanations": explanations,
            "missing_evidence": missing,
            "limitations": limitations,
        }
