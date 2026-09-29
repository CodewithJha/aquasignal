"""FHIR export error types — prefer refusal over fabricated resources."""

from __future__ import annotations


class FhirExportRefused(ValueError):
    """Raised when export is not allowed (e.g. not FINALIZED)."""


class StructuralGuardFailure(FhirExportRefused):
    """StructuralGuard refused export — missing preconditions or invariants."""


class UnsupportedOahMapping(FhirExportRefused):
    """Internal field/value has no verified TemporaryOahSystem mapping."""


class MissingRequiredOahData(FhirExportRefused):
    """Required IG element cannot be populated from packet/snapshot data."""


class FhirValidationFailure(FhirExportRefused):
    """Optional external validator rejected the Bundle."""


class FhirValidatorUnavailable(RuntimeError):
    """Optional validator port is configured but not reachable."""
