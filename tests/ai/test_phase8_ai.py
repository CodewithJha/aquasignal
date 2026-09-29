"""Phase 8 — AiAssistPort contracts (Null, Fake, provider adapter). Offline-safe."""

from __future__ import annotations

from typing import Any

import pytest

from app.ai.config import AiSettings
from app.ai.errors import AiAssistTimeout, AiAssistUnavailable
from app.ai.factory import build_ai_assist
from app.ai.fake import FakeAiAssist
from app.ai.null import NullAiAssist
from app.ai.provider import OptionalProviderAiAssist
from app.ai.prompts import PROMPT_VERSION
from app.ai.validate import (
    pack_suggestions_for_domain,
    suggestion_value,
    validate_suggestions_payload,
)
from app.domain.enums import Severity
from app.domain.packet import ObservationPacket
from app.domain.value_objects import QualityFlag, SiteRef


def _packet() -> ObservationPacket:
    return ObservationPacket.create(
        SiteRef(site_id="ghent", city="Ghent", display_name="Ghent, Belgium")
    )


def test_null_ai_suggest_enums_empty() -> None:
    ai = NullAiAssist()
    suggestions = ai.suggest_enums(_packet())
    assert suggestions.model_id == "null"
    assert suggestions.provider == "null"
    assert suggestions.items == {}
    assert ai.explain_flags(_packet(), []) == []


def test_fake_suggests_empty_sensory_fields() -> None:
    ai = FakeAiAssist()
    out = ai.suggest_enums(_packet())
    assert out.provider == "fake"
    assert out.prompt_version == PROMPT_VERSION
    assert "foam" in out.items
    assert suggestion_value(out.items["foam"]) == "absent"
    assert "foam" not in _packet().fields  # suggestions do not mutate packet


def test_fake_preset_and_vocab_reject() -> None:
    ai = FakeAiAssist(preset={"foam": "present", "bmwp": "42", "foam_bad": "nope"})
    out = ai.suggest_enums(_packet())
    assert suggestion_value(out.items.get("foam")) == "present"
    assert "bmwp" not in out.items


def test_validate_rejects_invalid_schema_and_vocab() -> None:
    validated = validate_suggestions_payload(
        {
            "suggestions": [
                {"field": "foam", "suggested_value": "not-a-value"},
                {"field": "pathogen", "suggested_value": "yes"},
                {"field": "colour", "suggested_value": "clear", "explanation": "ok"},
                {"field": "", "suggested_value": "clear"},
            ]
        },
        provider="test",
        model="m",
        prompt_version="v",
    )
    assert list(validated.items.keys()) == ["colour"]
    assert suggestion_value(validated.items["colour"]) == "clear"


def test_validate_rejects_prohibited_explanation() -> None:
    validated = validate_suggestions_payload(
        {
            "suggestions": [
                {
                    "field": "foam",
                    "suggested_value": "absent",
                    "explanation": "This implies BMWP is high",
                }
            ]
        },
        provider="test",
        model="m",
        prompt_version="v",
    )
    assert validated.items == {}


def test_fake_timeout_and_unavailable() -> None:
    with pytest.raises(AiAssistTimeout):
        FakeAiAssist(timeout=True).suggest_enums(_packet())
    with pytest.raises(AiAssistUnavailable):
        FakeAiAssist(fail=True).suggest_enums(_packet())


def test_fake_explain_flags_grounded() -> None:
    flag = QualityFlag(
        rule_id="completeness.foam",
        severity=Severity.SOFT_BLOCK_FINALIZE,
        code="MISSING_FOAM",
        message="Foam is required before finalize.",
        flag_id="flg_test",
    )
    explained = FakeAiAssist().explain_flags(_packet(), [flag])
    assert len(explained) == 1
    assert explained[0].severity == Severity.SOFT_BLOCK_FINALIZE.value
    assert explained[0].code == "MISSING_FOAM"
    assert "Foam is required" in explained[0].source_message
    assert explained[0].flag_id == "flg_test"


def test_provider_adapter_with_injected_http() -> None:
    calls: list[dict[str, Any]] = []

    class _Resp:
        status_code = 200

        def json(self) -> dict[str, Any]:
            return {
                "choices": [
                    {
                        "message": {
                            "content": '{"suggestions":[{"field":"foam","suggested_value":"absent","explanation":"advisory"}]}'
                        }
                    }
                ]
            }

    def fake_post(url, json=None, headers=None, timeout=None):
        calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Bearer ")
        # Ensure we never accidentally assert-print the key elsewhere in tests.
        return _Resp()

    ai = OptionalProviderAiAssist(
        api_key="test-key-not-for-prod",
        model="test-model",
        timeout_seconds=2.0,
        http_post=fake_post,
    )
    out = ai.suggest_enums(_packet())
    assert suggestion_value(out.items["foam"]) == "absent"
    assert len(calls) == 1
    assert calls[0]["timeout"] == 2.0


def test_provider_http_error_raises_unavailable() -> None:
    class _Resp:
        status_code = 429

        def json(self) -> dict[str, Any]:
            return {}

    ai = OptionalProviderAiAssist(
        api_key="k",
        model="m",
        http_post=lambda *a, **k: _Resp(),
    )
    with pytest.raises(AiAssistUnavailable):
        ai.suggest_enums(_packet())


def test_factory_defaults_and_fallbacks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AI_PROVIDER", raising=False)
    monkeypatch.delenv("AI_API_KEY", raising=False)
    assert isinstance(build_ai_assist(AiSettings.from_env()), NullAiAssist)

    monkeypatch.setenv("AI_PROVIDER", "fake")
    assert isinstance(build_ai_assist(AiSettings.from_env()), FakeAiAssist)

    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.delenv("AI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert isinstance(build_ai_assist(AiSettings.from_env()), NullAiAssist)

    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("AI_API_KEY", "sk-test")
    built = build_ai_assist(AiSettings.from_env())
    assert isinstance(built, OptionalProviderAiAssist)

    monkeypatch.setenv("AI_PROVIDER", "nonsense")
    assert isinstance(build_ai_assist(AiSettings.from_env()), NullAiAssist)


def test_pack_suggestions_includes_flag_explanations() -> None:
    from app.ai.port import FlagExplanation, Suggestions

    s = Suggestions(
        items={"foam": {"suggested_value": "absent"}},
        flag_explanations=[
            FlagExplanation(
                flag_id="f1",
                rule_id="r",
                code="C",
                severity="warn",
                source_message="src",
                explanation="exp",
            )
        ],
    )
    packed = pack_suggestions_for_domain(s)
    assert "foam" in packed
    assert "__flag_explanations__" in packed
