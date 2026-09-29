"""EXIF consistency rules — evaluate only when media context is bound."""

from __future__ import annotations

from app.domain.enums import Severity
from app.domain.packet import ObservationPacket
from app.domain.value_objects import QualityFlag
from app.flags.ports import MediaContextProvider, NullMediaContextProvider
from app.flags.rules.base import build_flag
from app.flags.schema import FieldSchema

# Rough threshold (~1 km) for claimed vs EXIF GPS disagreement.
_GPS_DELTA_DEG = 0.01


class ExifRule:
    rule_id_prefix = "exif"

    def __init__(
        self, media_provider: MediaContextProvider | None = None
    ) -> None:
        self._media = media_provider or NullMediaContextProvider()

    def evaluate(
        self, packet: ObservationPacket, *, schema: FieldSchema
    ) -> list[QualityFlag]:
        _ = schema
        ctx = self._media.for_packet(packet)
        if not ctx.bound:
            return []

        flags: list[QualityFlag] = []
        for asset in ctx.assets:
            if not asset.exif_available:
                continue
            if (
                asset.claimed_lat is not None
                and asset.claimed_lon is not None
                and asset.exif_lat is not None
                and asset.exif_lon is not None
            ):
                dlat = abs(asset.claimed_lat - asset.exif_lat)
                dlon = abs(asset.claimed_lon - asset.exif_lon)
                if dlat > _GPS_DELTA_DEG or dlon > _GPS_DELTA_DEG:
                    flags.append(
                        build_flag(
                            rule_id="exif.gps_mismatch",
                            severity=Severity.WARN,
                            code="EXIF_GPS_MISMATCH",
                            message=(
                                f"Media {asset.asset_id}: claimed GPS disagrees with "
                                "EXIF GPS. This does not prove observation truth."
                            ),
                            evidence_refs=(f"media.{asset.asset_id}.gps",),
                        )
                    )
        return flags
