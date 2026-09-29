"""Versionable PacketDocument DTO — JSON primitives only.

Explicit path: domain aggregate → PacketDocument → JSON text → DB.
No pickle. No secrets. No raw image bytes.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Mapping

from app.domain.enums import ActorType, FieldSource, Severity, WorkflowState
from app.domain.packet import ObservationPacket
from app.domain.value_objects import (
    Actor,
    ConfirmationSnapshot,
    FieldValue,
    QualityFlag,
    SiteRef,
)

# Bump when on-disk shape changes; migrations may rewrite rows.
PACKET_DOCUMENT_VERSION = 1


def _dt_to_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _dt_from_iso(value: str | None) -> datetime | None:
    if value is None:
        return None
    # fromisoformat handles "+00:00"; normalize Z
    normalized = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def field_to_dict(f: FieldValue) -> dict[str, Any]:
    return {
        "code": f.code,
        "value": f.value,
        "unit": f.unit,
        "source": f.source.value,
        "confidence": f.confidence,
    }


def field_from_dict(data: Mapping[str, Any]) -> FieldValue:
    return FieldValue(
        code=str(data["code"]),
        value=data["value"],
        unit=data.get("unit"),
        source=FieldSource(data["source"]),
        confidence=data.get("confidence"),
    )


def flag_to_dict(flag: QualityFlag) -> dict[str, Any]:
    return {
        "flag_id": flag.flag_id,
        "rule_id": flag.rule_id,
        "rule_version": flag.rule_version,
        "severity": flag.severity.value,
        "code": flag.code,
        "message": flag.message,
        "evidence_refs": list(flag.evidence_refs),
        "overridable": flag.overridable,
        "override_reason": flag.override_reason,
        "overridden_by": flag.overridden_by,
    }


def flag_from_dict(data: Mapping[str, Any]) -> QualityFlag:
    refs = data.get("evidence_refs") or []
    return QualityFlag(
        flag_id=str(data["flag_id"]),
        rule_id=str(data["rule_id"]),
        rule_version=str(data.get("rule_version") or "0.0.0"),
        severity=Severity(data["severity"]),
        code=str(data["code"]),
        message=str(data["message"]),
        evidence_refs=tuple(str(r) for r in refs),
        overridable=bool(data.get("overridable", True)),
        override_reason=data.get("override_reason"),
        overridden_by=data.get("overridden_by"),
    )


def site_to_dict(site: SiteRef) -> dict[str, Any]:
    return {
        "site_id": site.site_id,
        "city": site.city,
        "display_name": site.display_name,
        "lat": site.lat,
        "lon": site.lon,
        "fhir_location_identifier": site.fhir_location_identifier,
    }


def site_from_dict(data: Mapping[str, Any]) -> SiteRef:
    return SiteRef(
        site_id=str(data["site_id"]),
        city=str(data["city"]),
        display_name=str(data["display_name"]),
        lat=data.get("lat"),
        lon=data.get("lon"),
        fhir_location_identifier=data.get("fhir_location_identifier"),
    )


def actor_to_dict(actor: Actor) -> dict[str, Any]:
    return {"actor_type": actor.actor_type.value, "actor_id": actor.actor_id}


def actor_from_dict(data: Mapping[str, Any]) -> Actor:
    return Actor(ActorType(data["actor_type"]), str(data.get("actor_id") or "anonymous"))


def confirmation_to_dict(snap: ConfirmationSnapshot) -> dict[str, Any]:
    return {
        "fields": [field_to_dict(f) for f in snap.fields],
        "confirmed_at": _dt_to_iso(snap.confirmed_at),
        "confirmed_by": actor_to_dict(snap.confirmed_by),
        "content_hash": snap.content_hash,
    }


def confirmation_from_dict(data: Mapping[str, Any]) -> ConfirmationSnapshot:
    fields = tuple(field_from_dict(f) for f in data["fields"])
    confirmed_at = _dt_from_iso(data["confirmed_at"])
    assert confirmed_at is not None
    return ConfirmationSnapshot(
        fields=fields,
        confirmed_at=confirmed_at,
        confirmed_by=actor_from_dict(data["confirmed_by"]),
        content_hash=str(data["content_hash"]),
    )


def packet_to_document(packet: ObservationPacket) -> dict[str, Any]:
    """Domain → versionable DTO (plain JSON primitives)."""
    confirmation = (
        confirmation_to_dict(packet.confirmation) if packet.confirmation else None
    )
    return {
        "document_version": PACKET_DOCUMENT_VERSION,
        "packet_id": packet.packet_id,
        "site": site_to_dict(packet.site),
        "author_actor_id": packet.author_actor_id,
        "submitter_display": packet.submitter_display,
        "effective_at": _dt_to_iso(packet.effective_at),
        "workflow_state": packet.workflow_state.value,
        "fields": {code: field_to_dict(fv) for code, fv in sorted(packet.fields.items())},
        "suggestions": dict(packet.suggestions),
        "flags": [flag_to_dict(f) for f in packet.flags],
        "flags_rules_version": packet.rule_engine_version,
        "confirmation": confirmation,
        "notes": packet.notes,
        "one_health_sentence": packet.one_health_sentence,
        "fhir_bundle_id": packet.fhir_bundle_id,
    }


def document_to_packet(
    doc: Mapping[str, Any], *, observer_ref: str | None = None
) -> ObservationPacket:
    """DTO → domain via rehydrate (no provenance emission).

    ``observer_ref`` lives in its own column, outside the versioned document.
    """
    version = int(doc.get("document_version", 1))
    if version != PACKET_DOCUMENT_VERSION:
        # Future: migrate document in place. Phase 4 only knows v1.
        raise ValueError(f"unsupported packet document_version {version}")

    fields_raw = doc.get("fields") or {}
    fields = {str(k): field_from_dict(v) for k, v in fields_raw.items()}
    flags = [flag_from_dict(f) for f in (doc.get("flags") or [])]
    confirmation = None
    if doc.get("confirmation"):
        confirmation = confirmation_from_dict(doc["confirmation"])

    return ObservationPacket.rehydrate(
        packet_id=str(doc["packet_id"]),
        site=site_from_dict(doc["site"]),
        workflow_state=WorkflowState(doc["workflow_state"]),
        author_actor_id=str(doc.get("author_actor_id") or "anonymous"),
        effective_at=_dt_from_iso(doc.get("effective_at")),
        submitter_display=doc.get("submitter_display"),
        fields=fields,
        suggestions=doc.get("suggestions") or {},
        flags=flags,
        confirmation=confirmation,
        notes=doc.get("notes"),
        one_health_sentence=doc.get("one_health_sentence"),
        fhir_bundle_id=doc.get("fhir_bundle_id"),
        rule_engine_version=doc.get("flags_rules_version"),
        observer_ref=observer_ref,
    )


def dumps_document(doc: Mapping[str, Any]) -> str:
    """Deterministic JSON for storage (sorted keys, compact separators)."""
    return json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def loads_document(text: str) -> dict[str, Any]:
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("packet document must be a JSON object")
    return data


def dumps_json_value(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def loads_json_value(text: str | None) -> Any:
    if text is None:
        return None
    return json.loads(text)
