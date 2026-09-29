"""Explicit internal-key → verified TemporaryOahSystem coding registry.

Not a generic framework. Only mappings verified in docs/FHIR-SPEC.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from app.fhir.errors import UnsupportedOahMapping
from app.fhir.versions import TEMPORARY_OAH_SYSTEM


@dataclass(frozen=True, slots=True)
class OahCoding:
    system: str
    code: str
    display: str

    def as_coding(self) -> dict[str, str]:
        return {
            "system": self.system,
            "code": self.code,
            "display": self.display,
        }

    def as_codeable_concept(self) -> dict:
        return {"coding": [self.as_coding()], "text": self.display}


def _c(code: str, display: str) -> OahCoding:
    return OahCoding(system=TEMPORARY_OAH_SYSTEM, code=code, display=display)


# Observation.code for simple ObservationIndicatorsOah resources.
OBSERVATION_CODE_BY_INTERNAL: Mapping[str, OahCoding] = {
    "foam": _c("foam", "Foam/colour/smell"),
    "macrophytes": _c("macrophytes", "Macrophytes"),
    "riparian_vegetation": _c("riparianVegetation", "Riparian vegetation"),
    # Exact TemporaryOahSystem spelling (ConceptMap comment says morphology).
    "hydromorphology": _c("morophology", "Morphology of the streams"),
}

# A/P/E and foam domain → MacrophytesIndicatorValueOahVs codes (also in CS).
_APE_VALUE: Mapping[str, OahCoding] = {
    "a": _c("absent", "Absent"),
    "absent": _c("absent", "Absent"),
    "none": _c("absent", "Absent"),
    "p": _c("present", "Present"),
    "present": _c("present", "Present"),
    "e": _c("extensive", "Extensive"),
    "extensive": _c("extensive", "Extensive"),
    # Domain foam vocab → verified extensive (documented in FHIR-SPEC).
    "abundant": _c("extensive", "Extensive"),
}

# Riparian: only exact OAH percent codes (no invented domain-bin equivalence).
_RIPARIAN_VALUE: Mapping[str, OahCoding] = {
    "0-20-percent": _c("0-20-percent", "0-20%"),
    "21-40-percent": _c("21-40-percent", "21-40%"),
    "41-60-percent": _c("41-60-percent", "41-60%"),
    "61-80-percent": _c("61-80-percent", "61-80%"),
    "81-100-percent": _c("81-100-percent", "81-100%"),
}

# colour / smell: no TemporaryOahSystem observation codes — annotation only.
ANNOTATION_ONLY_INTERNAL_KEYS: frozenset[str] = frozenset({"colour", "smell"})

# Present in protocol-lite but no verified coded Observation mapping yet.
UNSUPPORTED_CODED_INTERNAL_KEYS: frozenset[str] = frozenset(
    {
        "macrophytes_non_native",
        "riparian_non_native",
    }
)

SUPPORTED_CODED_INTERNAL_KEYS: frozenset[str] = frozenset(
    OBSERVATION_CODE_BY_INTERNAL.keys()
)


def normalize_token(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value).strip().lower()


def observation_code_for(internal_key: str) -> OahCoding:
    try:
        return OBSERVATION_CODE_BY_INTERNAL[internal_key]
    except KeyError as exc:
        raise UnsupportedOahMapping(
            f"No verified Observation.code mapping for internal key {internal_key!r}"
        ) from exc


def value_coding_for(internal_key: str, value: object) -> OahCoding:
    token = normalize_token(value)
    if internal_key in {"foam", "macrophytes", "hydromorphology"}:
        coding = _APE_VALUE.get(token)
        if coding is None:
            raise UnsupportedOahMapping(
                f"Value {value!r} for {internal_key!r} is not in verified "
                "TemporaryOahSystem absent/present/extensive set"
            )
        return coding
    if internal_key == "riparian_vegetation":
        coding = _RIPARIAN_VALUE.get(token)
        if coding is None:
            raise UnsupportedOahMapping(
                f"Riparian value {value!r} is not an OAH percent code "
                "(domain bins like 0-25 are not mapped — see FHIR-SPEC)"
            )
        return coding
    raise UnsupportedOahMapping(
        f"No verified value coding for internal key {internal_key!r}"
    )
