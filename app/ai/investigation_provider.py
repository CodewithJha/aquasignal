"""Optional HTTP Investigation Copilot — same OpenAI-compatible stack as AiAssist.

Failures never escalate to fail analysis. No secrets in logs.
"""

from __future__ import annotations

import logging

from app.ai.errors import AiAssistSchemaError, AiAssistTimeout, AiAssistUnavailable
from app.ai.http_chat import HttpPost, JsonChatClient, provider_label
from app.ai.investigation_port import AdvisoryBrief, InvestigationBriefInput
from app.ai.investigation_validate import (
    bounded_brief_for_prompt,
    hash_investigation_brief,
    validate_advisory_brief,
)
from app.ai.prompts import (
    INVESTIGATION_COPILOT_PROMPT_VERSION,
    INVESTIGATION_COPILOT_SYSTEM,
    build_investigation_copilot_user_payload,
)

logger = logging.getLogger("confirmgate.ai.investigation_provider")


class OptionalProviderInvestigationCopilot:
    """Advisory-only HTTP copilot. Shares AiSettings / key / timeout with AiAssist."""

    provider_name: str = "openai"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float = 8.0,
        base_url: str = "https://api.openai.com/v1",
        http_post: HttpPost | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("api_key required for OptionalProviderInvestigationCopilot")
        self.model_id = model
        self.provider_name = provider_label(base_url)
        self._client = JsonChatClient(
            api_key=api_key,
            model=model,
            timeout_seconds=timeout_seconds,
            base_url=base_url,
            http_post=http_post,
        )

    def advise(self, brief: InvestigationBriefInput) -> AdvisoryBrief:
        brief_hash = hash_investigation_brief(brief)
        user = build_investigation_copilot_user_payload(
            brief_hash=brief_hash,
            bounded=bounded_brief_for_prompt(brief),
        )
        try:
            content = self._client.chat_json(
                system=INVESTIGATION_COPILOT_SYSTEM,
                user=user,
                purpose="investigation_advisory",
            )
        except AiAssistTimeout:
            logger.warning(
                "ai.investigation.timeout",
                extra={
                    "model": self.model_id,
                    "input_brief_hash": brief_hash,
                    "prompt_version": INVESTIGATION_COPILOT_PROMPT_VERSION,
                },
            )
            return self._unavailable(brief_hash, "timeout", "Investigation advisory timed out.")
        except (AiAssistUnavailable, AiAssistSchemaError) as exc:
            logger.warning(
                "ai.investigation.unavailable",
                extra={
                    "model": self.model_id,
                    "input_brief_hash": brief_hash,
                    "error": type(exc).__name__,
                },
            )
            return self._unavailable(brief_hash, "unavailable", "Investigation advisory unavailable.")

        return validate_advisory_brief(
            content,
            brief=brief,
            provider=self.provider_name,
            model=self.model_id,
            prompt_version=INVESTIGATION_COPILOT_PROMPT_VERSION,
            input_brief_hash=brief_hash,
        )

    def _unavailable(self, brief_hash: str, status: str, notes: str) -> AdvisoryBrief:
        return AdvisoryBrief(
            provider=self.provider_name,
            model=self.model_id,
            prompt_version=INVESTIGATION_COPILOT_PROMPT_VERSION,
            input_brief_hash=brief_hash,
            validation_status=status,
            available=False,
            notes=notes,
        )
