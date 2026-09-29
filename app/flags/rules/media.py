"""Media evidence rules — never interpret photos as lab measurements."""

from __future__ import annotations

from app.domain.enums import Severity
from app.domain.packet import ObservationPacket
from app.domain.value_objects import QualityFlag
from app.flags.ports import MediaContext, MediaContextProvider, NullMediaContextProvider
from app.flags.rules.base import build_flag
from app.flags.schema import FieldSchema

_ALLOWED_MIME_PREFIXES = ("image/jpeg", "image/png", "image/webp", "image/heic")
_MIN_BYTES = 2_048  # extremely small images
_MIN_EDGE = 64


class MediaRule:
    rule_id_prefix = "media"

    def __init__(
        self, media_provider: MediaContextProvider | None = None
    ) -> None:
        self._media = media_provider or NullMediaContextProvider()

    def evaluate(
        self, packet: ObservationPacket, *, schema: FieldSchema
    ) -> list[QualityFlag]:
        ctx = self._media.for_packet(packet)
        if not ctx.bound:
            # Media subsystem not wired — honest no-op (no fake blur/pathogen flags).
            return []

        flags: list[QualityFlag] = []
        has_vegetation = any(c in packet.fields for c in schema.vegetation_codes)

        if has_vegetation and not ctx.assets:
            flags.append(
                build_flag(
                    rule_id="media.missing_bank_photo",
                    severity=Severity.SOFT_BLOCK_FINALIZE,
                    code="MEDIA_REQUIRED",
                    message=(
                        "Vegetation/riparian claims are present but no photo evidence "
                        "is attached. Photos are evidence only — not ecological truth."
                    ),
                    evidence_refs=("media",) + tuple(
                        f"fields.{c}"
                        for c in sorted(schema.vegetation_codes & set(packet.fields))
                    ),
                )
            )

        for asset in ctx.assets:
            flags.extend(self._validate_asset(asset.content_type, asset))
        return flags

    def _validate_asset(self, content_type: str, asset) -> list[QualityFlag]:
        flags: list[QualityFlag] = []
        ct = (content_type or "").lower().strip()
        if not any(ct.startswith(p) for p in _ALLOWED_MIME_PREFIXES):
            flags.append(
                build_flag(
                    rule_id="media.invalid_mime",
                    severity=Severity.HARD_REJECT,
                    code="MEDIA_MIME",
                    message=(
                        f"Media {asset.asset_id} has unsupported content type "
                        f"{content_type!r}."
                    ),
                    evidence_refs=(f"media.{asset.asset_id}",),
                )
            )
        if asset.byte_size is not None and asset.byte_size < _MIN_BYTES:
            flags.append(
                build_flag(
                    rule_id="media.too_small",
                    severity=Severity.SOFT_BLOCK_FINALIZE,
                    code="MEDIA_TOO_SMALL",
                    message=(
                        f"Media {asset.asset_id} is extremely small "
                        f"({asset.byte_size} bytes) and is unsuitable as evidence."
                    ),
                    evidence_refs=(f"media.{asset.asset_id}",),
                )
            )
        if asset.width is not None and asset.height is not None:
            if asset.width < _MIN_EDGE or asset.height < _MIN_EDGE:
                flags.append(
                    build_flag(
                        rule_id="media.tiny_dimensions",
                        severity=Severity.SOFT_BLOCK_FINALIZE,
                        code="MEDIA_TINY",
                        message=(
                            f"Media {asset.asset_id} dimensions "
                            f"{asset.width}x{asset.height} are too small for evidence."
                        ),
                        evidence_refs=(f"media.{asset.asset_id}",),
                    )
                )
        return flags


def evaluate_media_with_context(
    packet: ObservationPacket,
    ctx: MediaContext,
    *,
    schema: FieldSchema,
) -> list[QualityFlag]:
    """Helper for tests that inject a bound MediaContext without a provider."""

    class _Fixed:
        def for_packet(self, _packet: ObservationPacket) -> MediaContext:
            return ctx

    return MediaRule(media_provider=_Fixed()).evaluate(packet, schema=schema)
