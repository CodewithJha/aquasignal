"""FHIR export boundary. Never emits status=preliminary. Refuse non-FINALIZED."""

from app.fhir.errors import (
    FhirExportRefused,
    FhirValidationFailure,
    FhirValidatorUnavailable,
    MissingRequiredOahData,
    StructuralGuardFailure,
    UnsupportedOahMapping,
)
from app.fhir.exporter import FhirExportResult, export_bundle, export_bundle_with_meta
from app.fhir.guard import StructuralGuard, check_exportable
from app.fhir.mapper import OahFhirMapper
from app.fhir.versions import OAH_FHIR_MAPPER_VERSION

__all__ = [
    "FhirExportRefused",
    "FhirExportResult",
    "FhirValidationFailure",
    "FhirValidatorUnavailable",
    "MissingRequiredOahData",
    "OAH_FHIR_MAPPER_VERSION",
    "OahFhirMapper",
    "StructuralGuard",
    "StructuralGuardFailure",
    "UnsupportedOahMapping",
    "check_exportable",
    "export_bundle",
    "export_bundle_with_meta",
]
