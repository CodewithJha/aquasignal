"""Phase 8 architecture — AI isolated from FHIR / domain authority."""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
APP = REPO / "app"


def test_fhir_modules_do_not_import_ai() -> None:
    fhir_dir = APP / "fhir"
    for path in fhir_dir.rglob("*.py"):
        text = path.read_text()
        assert "app.ai" not in text
        assert "AiAssist" not in text


def test_domain_does_not_import_ai_providers() -> None:
    domain_dir = APP / "domain"
    for path in domain_dir.rglob("*.py"):
        text = path.read_text()
        assert "app.ai" not in text
        assert "from app.ai" not in text


def test_ai_modules_do_not_import_fhir_or_persistence() -> None:
    ai_dir = APP / "ai"
    for path in ai_dir.rglob("*.py"):
        text = path.read_text()
        assert "app.fhir" not in text
        assert "app.persistence" not in text


def test_prompts_not_in_routes_or_templates() -> None:
    routes = (APP / "web" / "routes.py").read_text()
    assert "ENUM_SUGGEST_SYSTEM" not in routes
    assert "You assist ConfirmGate" not in routes
    for path in (APP / "templates").rglob("*.html"):
        text = path.read_text()
        assert "ENUM_SUGGEST_SYSTEM" not in text
        assert "FLAG_EXPLAIN_SYSTEM" not in text


def test_null_ai_is_default_factory() -> None:
    from app.ai.config import AiSettings
    from app.ai.factory import build_ai_assist
    from app.ai.null import NullAiAssist

    ai = build_ai_assist(AiSettings(provider="null"))
    assert isinstance(ai, NullAiAssist)
