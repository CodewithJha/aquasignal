"""OpenAI-compatible JSON chat call shared by the optional HTTP providers.

One request, bounded by ``timeout_seconds``, no retries. Errors are mapped to
AiAssistTimeout / AiAssistUnavailable / AiAssistSchemaError. Headers (which
carry the API key) are never logged.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable
from urllib.parse import urlparse

from app.ai.errors import AiAssistSchemaError, AiAssistTimeout, AiAssistUnavailable

logger = logging.getLogger("confirmgate.ai.http")

HttpPost = Callable[..., Any]

OPENAI_HOST = "api.openai.com"


def provider_label(base_url: str) -> str:
    """Audit label for the configured endpoint: host only, never path or credentials."""
    host = (urlparse(base_url).hostname or "").lower()
    if host == OPENAI_HOST:
        return "openai"
    return f"openai-compatible:{host}" if host else "openai-compatible"


class JsonChatClient:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float,
        base_url: str,
        http_post: HttpPost | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout = timeout_seconds
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        self._http_post = http_post

    def chat_json(self, *, system: str, user: dict[str, Any], purpose: str) -> dict[str, Any]:
        body = {
            "model": self._model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(user, sort_keys=True)},
            ],
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        try:
            post = self._http_post or _httpx_post
            response = post(self._url, json=body, headers=headers, timeout=self._timeout)
        except Exception as exc:
            name = type(exc).__name__
            if "Timeout" in name or "timeout" in str(exc).lower():
                logger.warning("ai.http.timeout", extra={"purpose": purpose, "model": self._model})
                raise AiAssistTimeout(str(exc)) from exc
            logger.warning(
                "ai.http.unavailable",
                extra={"purpose": purpose, "model": self._model, "error": name},
            )
            raise AiAssistUnavailable(str(exc)) from exc

        status = getattr(response, "status_code", None)
        if status is not None and int(status) >= 400:
            logger.warning(
                "ai.http.error_status",
                extra={"purpose": purpose, "status": status, "model": self._model},
            )
            raise AiAssistUnavailable(f"HTTP {status}")

        try:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            parsed = content if isinstance(content, dict) else json.loads(content)
        except Exception as exc:
            raise AiAssistSchemaError(str(exc)) from exc
        if not isinstance(parsed, dict):
            raise AiAssistSchemaError("provider content is not a JSON object")
        return parsed


def _httpx_post(url: str, **kwargs: Any) -> Any:
    import httpx

    return httpx.post(url, **kwargs)
