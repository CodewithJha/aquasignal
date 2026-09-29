"""Seeded OAH sites — single catalog for domain + citizen UX.

City names constrained by ``OAH_CITIES``. Web/forms must use this catalog
(or ``get_site`` / ``list_sites``) rather than duplicating city lists.
"""

from __future__ import annotations

from app.domain.cities import OAH_CITIES
from app.domain.errors import DomainValidationError
from app.domain.value_objects import SiteRef

# Official five OAH demo cities. Identifiers are opaque site ids for the demo;
# FHIR Location.identifier.value uses the same id with the verified IG system
# (see docs/FHIR-SPEC.md) — applied at mapper time, not invented here.
_SEED: tuple[SiteRef, ...] = (
    SiteRef(
        site_id="coimbra",
        city="Coimbra",
        display_name="Coimbra, Portugal",
        fhir_location_identifier="coimbra",
        lat=40.2033,
        lon=-8.4103,
    ),
    SiteRef(
        site_id="benevento",
        city="Benevento",
        display_name="Benevento, Italy",
        fhir_location_identifier="benevento",
        lat=41.1297,
        lon=14.7826,
    ),
    SiteRef(
        site_id="ghent",
        city="Ghent",
        display_name="Ghent, Belgium",
        fhir_location_identifier="ghent",
        lat=51.0543,
        lon=3.7174,
    ),
    SiteRef(
        site_id="oslo",
        city="Oslo",
        display_name="Oslo, Norway",
        fhir_location_identifier="oslo",
        lat=59.9139,
        lon=10.7522,
    ),
    SiteRef(
        site_id="toulouse",
        city="Toulouse",
        display_name="Toulouse, France",
        fhir_location_identifier="toulouse",
        lat=43.6047,
        lon=1.4442,
    ),
)

# Fail closed if seed drifts from OAH_CITIES.
assert {s.city for s in _SEED} == set(OAH_CITIES), "seed sites must match OAH_CITIES"
assert len(_SEED) == len(OAH_CITIES)

SEED_SITES: dict[str, SiteRef] = {s.site_id: s for s in _SEED}


def list_sites() -> tuple[SiteRef, ...]:
    """Stable ordered list for form selects."""
    return _SEED


def get_site(site_id: str) -> SiteRef:
    """Resolve a seeded site by opaque id. Raises DomainValidationError if unknown."""
    key = (site_id or "").strip().lower()
    site = SEED_SITES.get(key)
    if site is None:
        raise DomainValidationError(
            f"site_id must be one of {sorted(SEED_SITES)}; got {site_id!r}"
        )
    return site
