"""Geographic eligibility/consistency against seeded SiteRef (no geocoding APIs)."""

from __future__ import annotations

from app.domain.cities import OAH_CITIES
from app.domain.enums import Severity
from app.domain.packet import ObservationPacket
from app.domain.value_objects import QualityFlag
from app.flags.rules.base import build_flag
from app.flags.schema import FieldSchema


class GeoRule:
    rule_id_prefix = "geo"

    def evaluate(
        self, packet: ObservationPacket, *, schema: FieldSchema
    ) -> list[QualityFlag]:
        flags: list[QualityFlag] = []
        site = packet.site

        if site.city not in OAH_CITIES:
            flags.append(
                build_flag(
                    rule_id="geo.unsupported_city",
                    severity=Severity.HARD_REJECT,
                    code="GEO_UNSUPPORTED_CITY",
                    message=(
                        f"City {site.city!r} is not one of the five OAH demo cities."
                    ),
                    evidence_refs=("site.city",),
                    overridable=False,
                )
            )

        if not site.site_id.strip():
            flags.append(
                build_flag(
                    rule_id="geo.missing_site_id",
                    severity=Severity.HARD_REJECT,
                    code="GEO_MISSING_SITE",
                    message="Site reference is missing a site_id.",
                    evidence_refs=("site.site_id",),
                    overridable=False,
                )
            )

        # Coordinates are optional; GPS does not prove ecological truth.
        if (site.lat is None) != (site.lon is None):
            flags.append(
                build_flag(
                    rule_id="geo.partial_coordinates",
                    severity=Severity.WARN,
                    code="GEO_PARTIAL_COORDS",
                    message=(
                        "Site has only one of lat/lon set. Provide both or neither; "
                        "coordinates do not prove observation truth."
                    ),
                    evidence_refs=("site.lat", "site.lon"),
                )
            )

        if site.lat is not None and site.lon is not None:
            if not (-90.0 <= site.lat <= 90.0 and -180.0 <= site.lon <= 180.0):
                flags.append(
                    build_flag(
                        rule_id="geo.invalid_coordinates",
                        severity=Severity.HARD_REJECT,
                        code="GEO_INVALID_COORDS",
                        message="Site lat/lon are outside valid geographic ranges.",
                        evidence_refs=("site.lat", "site.lon"),
                    )
                )
        return flags
