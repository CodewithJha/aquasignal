"""Optional FHIR validator port — core export works without a validator."""

from __future__ import annotations

from typing import Any, Protocol

from app.fhir.errors import FhirValidationFailure, FhirValidatorUnavailable


class FhirValidatorPort(Protocol):
    def validate_bundle(self, bundle: dict[str, Any]) -> None:
        """Raise FhirValidationFailure if Bundle is invalid per the adapter."""
        ...


class NullFhirValidator:
    """No-op validator — always available; does not claim IG conformance."""

    def validate_bundle(self, bundle: dict[str, Any]) -> None:
        _ = bundle
        return None


class UnavailableFhirValidator:
    """Configured but unreachable external validator (tests / future adapter)."""

    def validate_bundle(self, bundle: dict[str, Any]) -> None:
        _ = bundle
        raise FhirValidatorUnavailable(
            "FHIR IG validator is configured but unavailable"
        )


class RejectingFhirValidator:
    """Test double that always fails validation."""

    def __init__(self, message: str = "bundle rejected by test validator") -> None:
        self.message = message

    def validate_bundle(self, bundle: dict[str, Any]) -> None:
        _ = bundle
        raise FhirValidationFailure(self.message)
