"""Null Investigation Copilot — zero API keys, zero external calls."""

from __future__ import annotations

from app.ai.investigation_port import AdvisoryBrief, InvestigationBriefInput
from app.ai.investigation_validate import hash_investigation_brief
from app.ai.prompts import INVESTIGATION_COPILOT_PROMPT_VERSION


class NullInvestigationCopilot:
    """Default. Demo works with AI off; advisory section stays unavailable."""

    model_id: str = "null"
    provider_name: str = "null"

    def advise(self, brief: InvestigationBriefInput) -> AdvisoryBrief:
        return AdvisoryBrief(
            summary="",
            signal_explanations=[],
            missing_evidence=[],
            limitations=[],
            provider=self.provider_name,
            model=self.model_id,
            prompt_version=INVESTIGATION_COPILOT_PROMPT_VERSION,
            input_brief_hash=hash_investigation_brief(brief),
            validation_status="null",
            available=False,
            notes=(
                "NullInvestigationCopilot: no advisory. "
                "SYSTEM ANALYSIS and human review remain authority."
            ),
        )
