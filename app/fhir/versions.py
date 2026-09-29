"""Canonical mapper version for OAH FHIR export (HITL Q7)."""

from __future__ import annotations

OAH_FHIR_MAPPER_VERSION = "0.1.1"

# Verified against hl7-eu/oah CI-build 0.1.0-ci-build (2026-09-21).
OAH_IG_VERSION = "0.1.0-ci-build"
OAH_FHIR_VERSION = "4.0.1"

PROFILE_LOCATION_OAH = (
    "http://hl7.eu/fhir/ig/oah/StructureDefinition/location-oah"
)
PROFILE_OBSERVATION_INDICATORS_OAH = (
    "http://hl7.eu/fhir/ig/oah/StructureDefinition/observation-indicators-oah"
)
# Deferred in Phase 5 — typed components required (see docs/FHIR-SPEC.md).
PROFILE_OBSERVATION_WITH_COMP_OAH = (
    "http://hl7.eu/fhir/ig/oah/StructureDefinition/observation-with-component-oah"
)

TEMPORARY_OAH_SYSTEM = (
    "http://hl7.eu/fhir/ig/oah/CodeSystem/temporarySystem-oah-eu"
)

# From IG Location examples (loc_benevento.fsh, water_tmp.fsh) — not invented.
LOCATION_IDENTIFIER_SYSTEM = "https://oneaquahealth.eu/location-id"
