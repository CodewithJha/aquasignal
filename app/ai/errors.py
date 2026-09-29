"""AI assist errors — never escalate to fail citizen submission."""

from __future__ import annotations


class AiAssistError(Exception):
    """Base class for optional AI failures."""

    def __init__(self, message: str = "AI assistance unavailable") -> None:
        self.user_message = "AI assistance unavailable"
        super().__init__(message)


class AiAssistUnavailable(AiAssistError):
    """Provider missing, HTTP error, or rate limit."""


class AiAssistTimeout(AiAssistError):
    """Bounded timeout exceeded."""


class AiAssistSchemaError(AiAssistError):
    """Malformed or schema-invalid provider output."""
