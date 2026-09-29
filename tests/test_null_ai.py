"""NullAiAssist works with no API keys and no network."""

from __future__ import annotations

from app.ai.null import NullAiAssist
from app.domain.packet import ObservationPacket
from app.domain.value_objects import SiteRef


def _packet() -> ObservationPacket:
    return ObservationPacket.create(
        SiteRef(site_id="ghent", city="Ghent", display_name="Ghent, Belgium")
    )


def test_null_ai_suggest_enums_empty() -> None:
    ai = NullAiAssist()
    suggestions = ai.suggest_enums(_packet())
    assert suggestions.model_id == "null"
    assert suggestions.items == {}


def test_null_ai_assess_photo_no_flags() -> None:
    ai = NullAiAssist()
    assessment = ai.assess_photo_protocol(media=None)
    assert assessment.model_id == "null"
    assert assessment.flags == []


def test_null_ai_glossary_returns_text() -> None:
    ai = NullAiAssist()
    text = ai.glossary("foam")
    assert "NullAiAssist" in text
    assert "foam" in text


def test_null_ai_explain_flags_empty() -> None:
    ai = NullAiAssist()
    assert ai.explain_flags(_packet(), []) == []
    assert ai.provider_name == "null"
