"""P2 — provider label reflects AI_BASE_URL host instead of a hardcoded 'openai'."""

from __future__ import annotations

import pytest

from app.ai.http_chat import provider_label
from app.ai.investigation_provider import OptionalProviderInvestigationCopilot
from app.ai.provider import OptionalProviderAiAssist


@pytest.mark.parametrize(
    ("base_url", "expected"),
    [
        ("https://api.openai.com/v1", "openai"),
        ("https://API.OpenAI.com/v1/", "openai"),
        ("https://api.featherless.ai/v1", "openai-compatible:api.featherless.ai"),
        ("http://localhost:11434/v1", "openai-compatible:localhost"),
        ("https://user:secret@proxy.example/v1?key=x", "openai-compatible:proxy.example"),
        ("not a url", "openai-compatible"),
    ],
)
def test_provider_label(base_url: str, expected: str) -> None:
    assert provider_label(base_url) == expected


def test_providers_use_label_from_base_url() -> None:
    url = "https://api.featherless.ai/v1"
    assist = OptionalProviderAiAssist(api_key="k", model="m", base_url=url)
    copilot = OptionalProviderInvestigationCopilot(api_key="k", model="m", base_url=url)
    assert assist.provider_name == "openai-compatible:api.featherless.ai"
    assert copilot.provider_name == "openai-compatible:api.featherless.ai"


def test_default_base_url_still_labelled_openai() -> None:
    assert OptionalProviderAiAssist(api_key="k", model="m").provider_name == "openai"
