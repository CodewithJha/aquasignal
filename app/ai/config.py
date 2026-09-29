"""AI configuration from environment. Defaults to Null — no network."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AiSettings:
    """Composition-root config. Secrets never enter provenance or logs."""

    provider: str = "null"
    model: str = "gpt-4o-mini"
    api_key: str | None = None
    timeout_seconds: float = 8.0
    base_url: str = "https://api.openai.com/v1"

    @classmethod
    def from_env(cls) -> AiSettings:
        provider = (os.environ.get("AI_PROVIDER") or "null").strip().lower()
        model = (os.environ.get("AI_MODEL") or "gpt-4o-mini").strip()
        raw_timeout = (os.environ.get("AI_TIMEOUT") or "8").strip()
        try:
            timeout = float(raw_timeout)
        except ValueError:
            timeout = 8.0
        timeout = max(1.0, min(timeout, 30.0))
        api_key = os.environ.get("AI_API_KEY") or os.environ.get("OPENAI_API_KEY")
        if api_key is not None:
            api_key = api_key.strip() or None
        base_url = (
            os.environ.get("AI_BASE_URL") or "https://api.openai.com/v1"
        ).strip()
        return cls(
            provider=provider or "null",
            model=model or "gpt-4o-mini",
            api_key=api_key,
            timeout_seconds=timeout,
            base_url=base_url.rstrip("/"),
        )

    @property
    def is_null(self) -> bool:
        return self.provider in {"", "null", "none", "off"}

    @property
    def is_fake(self) -> bool:
        return self.provider == "fake"

    @property
    def wants_http_provider(self) -> bool:
        return self.provider in {"openai", "http", "provider"}
