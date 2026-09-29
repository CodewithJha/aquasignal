"""Select AiAssistPort + InvestigationCopilotPort from shared AiSettings.

Default Null — no network. One provider system; two ports.
"""

from __future__ import annotations

import logging

from app.ai.config import AiSettings
from app.ai.fake import FakeAiAssist
from app.ai.investigation_fake import FakeInvestigationCopilot
from app.ai.investigation_null import NullInvestigationCopilot
from app.ai.investigation_port import InvestigationCopilotPort
from app.ai.investigation_provider import OptionalProviderInvestigationCopilot
from app.ai.null import NullAiAssist
from app.ai.port import AiAssistPort
from app.ai.provider import OptionalProviderAiAssist

logger = logging.getLogger("confirmgate.ai.factory")


def build_ai_assist(settings: AiSettings | None = None) -> AiAssistPort:
    """Composition helper. Invalid/unset provider → NullAiAssist."""
    cfg = settings or AiSettings.from_env()

    if cfg.is_null:
        logger.info("ai.factory.null", extra={"provider": "null"})
        return NullAiAssist()

    if cfg.is_fake:
        logger.info("ai.factory.fake", extra={"provider": "fake"})
        return FakeAiAssist()

    if cfg.wants_http_provider:
        if not cfg.api_key:
            logger.warning(
                "ai.factory.fallback_null",
                extra={"reason": "missing_api_key", "requested": cfg.provider},
            )
            return NullAiAssist()
        logger.info(
            "ai.factory.provider",
            extra={
                "provider": cfg.provider,
                "model": cfg.model,
                "timeout": cfg.timeout_seconds,
                # never log api_key
            },
        )
        return OptionalProviderAiAssist(
            api_key=cfg.api_key,
            model=cfg.model,
            timeout_seconds=cfg.timeout_seconds,
            base_url=cfg.base_url,
        )

    logger.warning(
        "ai.factory.fallback_null",
        extra={"reason": "unknown_provider", "requested": cfg.provider},
    )
    return NullAiAssist()


def build_investigation_copilot(
    settings: AiSettings | None = None,
) -> InvestigationCopilotPort:
    """Same AiSettings selection as build_ai_assist — Null-first."""
    cfg = settings or AiSettings.from_env()

    if cfg.is_null:
        logger.info("ai.investigation.factory.null", extra={"provider": "null"})
        return NullInvestigationCopilot()

    if cfg.is_fake:
        logger.info("ai.investigation.factory.fake", extra={"provider": "fake"})
        return FakeInvestigationCopilot()

    if cfg.wants_http_provider:
        if not cfg.api_key:
            logger.warning(
                "ai.investigation.factory.fallback_null",
                extra={"reason": "missing_api_key", "requested": cfg.provider},
            )
            return NullInvestigationCopilot()
        logger.info(
            "ai.investigation.factory.provider",
            extra={
                "provider": cfg.provider,
                "model": cfg.model,
                "timeout": cfg.timeout_seconds,
            },
        )
        return OptionalProviderInvestigationCopilot(
            api_key=cfg.api_key,
            model=cfg.model,
            timeout_seconds=cfg.timeout_seconds,
            base_url=cfg.base_url,
        )

    logger.warning(
        "ai.investigation.factory.fallback_null",
        extra={"reason": "unknown_provider", "requested": cfg.provider},
    )
    return NullInvestigationCopilot()
