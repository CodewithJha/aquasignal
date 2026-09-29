"""Composition root — wire production/demo dependencies once.

Production/demo uses DeterministicFlagEngine (not NullFlagEngine).
NullFlagEngine remains available for isolated unit tests.

Auth is not implemented — demo reviewer Actor is injected for Phase 7.
AI defaults to NullAiAssist via AI_PROVIDER (no network / no API key).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from app.ai.config import AiSettings
from app.ai.factory import build_ai_assist, build_investigation_copilot
from app.ai.port import AiAssistPort
from app.ai.investigation_port import InvestigationCopilotPort
from app.application.analysis_service import AnalysisService
from app.application.citizen_flow import CitizenFlowService
from app.application.investigation_brief import InvestigationBriefService
from app.application.investigation_service import InvestigationService
from app.application.reviewer_flow import (
    DEMO_REVIEWER_ACTOR_ID,
    ReviewerFlowService,
)
from app.application.service import ObservationService
from app.fhir.validator import FhirValidatorPort, NullFhirValidator
from app.flags.engine import DeterministicFlagEngine, FlagEngine
from app.persistence.config import DatabaseSettings
from app.persistence.duplicate_lookup import SqliteDuplicateLookup
from app.persistence.factory import database_reachable, open_unit_of_work
from app.signals.engine import SignalEngine

logger = logging.getLogger("confirmgate.composition")

REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass(slots=True)
class AppServices:
    """Process-scoped services for the FastAPI app."""

    settings: DatabaseSettings
    observation: ObservationService
    flow: CitizenFlowService
    reviewer: ReviewerFlowService
    analysis: AnalysisService
    investigation: InvestigationService
    brief: InvestigationBriefService
    flag_engine: FlagEngine
    ai: AiAssistPort
    investigation_copilot: InvestigationCopilotPort
    fhir_validator: FhirValidatorPort
    ai_settings: AiSettings


_SERVICES: AppServices | None = None


def build_services(
    *,
    settings: DatabaseSettings | None = None,
    flag_engine: FlagEngine | None = None,
    ai: AiAssistPort | None = None,
    investigation_copilot: InvestigationCopilotPort | None = None,
    fhir_validator: FhirValidatorPort | None = None,
    reviewer_actor_id: str = DEMO_REVIEWER_ACTOR_ID,
    ai_settings: AiSettings | None = None,
) -> AppServices:
    """Construct the modular monolith graph (idempotent helpers for tests)."""
    resolved_settings = settings or DatabaseSettings.from_env(project_root=REPO_ROOT)
    migration_conn, uow_factory = open_unit_of_work(resolved_settings)
    migration_conn.close()

    if flag_engine is None:
        flag_engine = DeterministicFlagEngine(
            duplicate_lookup=SqliteDuplicateLookup(resolved_settings)
        )
    resolved_ai_settings = ai_settings or AiSettings.from_env()
    resolved_ai = ai if ai is not None else build_ai_assist(resolved_ai_settings)
    resolved_copilot = (
        investigation_copilot
        if investigation_copilot is not None
        else build_investigation_copilot(resolved_ai_settings)
    )
    resolved_validator = fhir_validator or NullFhirValidator()

    observation = ObservationService(uow_factory, flag_engine=flag_engine)
    flow = CitizenFlowService(
        observation,
        ai=resolved_ai,
        fhir_validator=resolved_validator,
    )
    reviewer = ReviewerFlowService(
        observation,
        reviewer_actor_id=reviewer_actor_id,
    )
    analysis = AnalysisService(uow_factory, signal_engine=SignalEngine())
    investigation = InvestigationService(uow_factory)
    brief = InvestigationBriefService(uow_factory)
    logger.info(
        "composition.ready",
        extra={
            "flag_engine": type(flag_engine).__name__,
            "flag_engine_version": getattr(flag_engine, "version", None),
            "ai": type(resolved_ai).__name__,
            "ai_provider": getattr(resolved_ai, "provider_name", None),
            "ai_model": getattr(resolved_ai, "model_id", None),
            "investigation_copilot": type(resolved_copilot).__name__,
            "fhir_validator": type(resolved_validator).__name__,
            "database": resolved_settings.dialect,
            "sqlite": (
                str(resolved_settings.sqlite_path) if resolved_settings.sqlite_path else None
            ),
            "reviewer_actor_id": reviewer_actor_id,
            "detector_set_version": analysis.detector_set_version,
            "auth": "not_implemented",
        },
    )
    return AppServices(
        settings=resolved_settings,
        observation=observation,
        flow=flow,
        reviewer=reviewer,
        analysis=analysis,
        investigation=investigation,
        brief=brief,
        flag_engine=flag_engine,
        ai=resolved_ai,
        investigation_copilot=resolved_copilot,
        fhir_validator=resolved_validator,
        ai_settings=resolved_ai_settings,
    )


def get_services() -> AppServices:
    """Lazy process singleton — avoids opening SQLite on import for unit tests."""
    global _SERVICES
    if _SERVICES is None:
        _SERVICES = build_services()
    return _SERVICES


def check_database() -> bool:
    """Health probe for the configured database. Never raises."""
    try:
        services = get_services()
    except Exception:
        logger.exception("health.services_unavailable")
        return False
    return database_reachable(services.settings)


def reset_services() -> None:
    """Test helper — clear the process singleton."""
    global _SERVICES
    _SERVICES = None


def set_services(services: AppServices) -> None:
    """Test helper — inject an isolated graph."""
    global _SERVICES
    _SERVICES = services
