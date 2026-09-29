"""AquaSignal domain ↔ persistence row mappers.

Domain entities are reconstructed via domain factories / constructors so
invariants (fixture→synthetic, snapshot hash, actor rules) are re-enforced.
No sqlite types leak into domain.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from app.application.errors import SerializationFailure
from app.application.serialization import site_from_dict, site_to_dict
from app.domain.enums import ActorType
from app.domain.evidence.enums import EvidenceSourceClass, RelationType
from app.domain.evidence.item import EvidenceItem
from app.domain.evidence.relation import EvidenceRelation
from app.domain.evidence.snapshot import EvidenceSnapshot, compute_snapshot_hash
from app.domain.investigation.analysis_run import AnalysisRun
from app.domain.investigation.case import InvestigationCase
from app.domain.investigation.decision import HumanDecision
from app.domain.investigation.enums import AnalysisRunStatus, CaseState, DecisionCode
from app.domain.signal.enums import SignalType
from app.domain.signal.environmental import EnvironmentalSignal
from app.domain.signal.value_objects import DetectorId, DetectorVersion, TimeWindow
from app.domain.value_objects import Actor, SiteRef


def dt_to_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def dt_from_iso(value: str) -> datetime:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise SerializationFailure(f"invalid datetime: {value!r}") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def dumps_structured(value: Mapping[str, Any] | dict[str, Any]) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        raise SerializationFailure("failed to serialize structured JSON") from exc


def loads_structured(text: str) -> dict[str, Any]:
    try:
        data = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise SerializationFailure("failed to deserialize structured JSON") from exc
    if not isinstance(data, dict):
        raise SerializationFailure("structured JSON must be an object")
    return data


def site_columns(site: SiteRef) -> dict[str, Any]:
    d = site_to_dict(site)
    return {
        "site_id": d["site_id"],
        "city": d["city"],
        "display_name": d["display_name"],
        "lat": d.get("lat"),
        "lon": d.get("lon"),
        "fhir_location_identifier": d.get("fhir_location_identifier"),
    }


def site_from_columns(row: Mapping[str, Any]) -> SiteRef:
    return site_from_dict(
        {
            "site_id": row["site_id"],
            "city": row["city"],
            "display_name": row["display_name"],
            "lat": row["lat"],
            "lon": row["lon"],
            "fhir_location_identifier": row["fhir_location_identifier"],
        }
    )


def evidence_item_to_row(item: EvidenceItem) -> dict[str, Any]:
    # Enforce fixture→synthetic on the save path via domain factory round-trip.
    verified = EvidenceItem.create(
        evidence_id=item.evidence_id,
        source_class=item.source_class,
        site=item.site,
        observed_at=item.observed_at,
        payload_ref=item.payload_ref,
        content_hash=item.content_hash,
        license_tag=item.license_tag,
        is_synthetic=item.is_synthetic,
        fields=item.fields,
    )
    row = site_columns(verified.site)
    row.update(
        {
            "evidence_id": verified.evidence_id,
            "source_class": verified.source_class.value,
            "observed_at": dt_to_iso(verified.observed_at),
            "payload_ref": verified.payload_ref,
            "content_hash": verified.content_hash,
            "license_tag": verified.license_tag,
            "is_synthetic": 1 if verified.is_synthetic else 0,
            "fields_json": dumps_structured(dict(verified.fields)),
        }
    )
    return row


def evidence_item_from_row(row: Mapping[str, Any]) -> EvidenceItem:
    try:
        raw_fields = row["fields_json"] if "fields_json" in row.keys() else "{}"
        if raw_fields is None or raw_fields == "":
            fields: dict[str, str] = {}
        else:
            parsed = loads_structured(str(raw_fields))
            fields = {str(k): str(v) for k, v in parsed.items()}
        return EvidenceItem.create(
            evidence_id=str(row["evidence_id"]),
            source_class=EvidenceSourceClass(str(row["source_class"])),
            site=site_from_columns(row),
            observed_at=dt_from_iso(str(row["observed_at"])),
            payload_ref=str(row["payload_ref"]),
            content_hash=str(row["content_hash"]),
            license_tag=str(row["license_tag"]),
            is_synthetic=bool(int(row["is_synthetic"])),
            fields=fields,
        )
    except SerializationFailure:
        raise
    except Exception as exc:  # domain validation / enum
        raise SerializationFailure(
            f"failed to map evidence_item {row.get('evidence_id')}"
        ) from exc


def evidence_snapshot_to_parts(
    snapshot: EvidenceSnapshot,
) -> tuple[dict[str, Any], tuple[str, ...]]:
    # Recompute hash via domain; refuse silent hash drift.
    rebuilt = EvidenceSnapshot.create(
        ordered_evidence_ids=snapshot.ordered_evidence_ids,
        source_manifest=snapshot.source_manifest,
        created_at=snapshot.created_at,
        snapshot_id=snapshot.snapshot_id,
    )
    if rebuilt.snapshot_hash != snapshot.snapshot_hash:
        raise SerializationFailure(
            "snapshot_hash does not match ordered evidence ids + manifest"
        )
    row = {
        "snapshot_id": rebuilt.snapshot_id,
        "snapshot_hash": rebuilt.snapshot_hash,
        "created_at": dt_to_iso(rebuilt.created_at),
        "source_manifest_json": dumps_structured(dict(rebuilt.source_manifest)),
    }
    return row, rebuilt.ordered_evidence_ids


def evidence_snapshot_from_parts(
    row: Mapping[str, Any],
    ordered_evidence_ids: Sequence[str],
) -> EvidenceSnapshot:
    try:
        manifest = loads_structured(str(row["source_manifest_json"]))
        ids = tuple(str(eid) for eid in ordered_evidence_ids)
        stored_hash = str(row["snapshot_hash"])
        expected = compute_snapshot_hash(ids, manifest)
        if stored_hash != expected:
            raise SerializationFailure(
                "stored snapshot_hash does not match reconstructed digest"
            )
        return EvidenceSnapshot.create(
            ordered_evidence_ids=ids,
            source_manifest=manifest,
            created_at=dt_from_iso(str(row["created_at"])),
            snapshot_id=str(row["snapshot_id"]),
        )
    except SerializationFailure:
        raise
    except Exception as exc:
        raise SerializationFailure(
            f"failed to map evidence_snapshot {row.get('snapshot_id')}"
        ) from exc


def evidence_relation_to_row(rel: EvidenceRelation) -> dict[str, Any]:
    verified = EvidenceRelation.create(
        relation_id=rel.relation_id,
        relation_type=rel.relation_type,
        left_ref=rel.left_ref,
        right_ref=rel.right_ref,
        analysis_run_id=rel.analysis_run_id,
        rationale_code=rel.rationale_code,
        message=rel.message,
    )
    return {
        "relation_id": verified.relation_id,
        "relation_type": verified.relation_type.value,
        "left_ref": verified.left_ref,
        "right_ref": verified.right_ref,
        "analysis_run_id": verified.analysis_run_id,
        "rationale_code": verified.rationale_code,
        "message": verified.message,
    }


def evidence_relation_from_row(row: Mapping[str, Any]) -> EvidenceRelation:
    try:
        return EvidenceRelation.create(
            relation_id=str(row["relation_id"]),
            relation_type=RelationType(str(row["relation_type"])),
            left_ref=str(row["left_ref"]),
            right_ref=str(row["right_ref"]),
            analysis_run_id=str(row["analysis_run_id"]),
            rationale_code=str(row["rationale_code"]),
            message=str(row["message"]),
        )
    except Exception as exc:
        raise SerializationFailure(
            f"failed to map evidence_relation {row.get('relation_id')}"
        ) from exc


def environmental_signal_to_parts(
    signal: EnvironmentalSignal,
) -> tuple[dict[str, Any], tuple[str, ...]]:
    verified = EnvironmentalSignal.create(
        signal_id=signal.signal_id,
        detector_id=signal.detector_id,
        detector_version=signal.detector_version,
        signal_type=signal.signal_type,
        site=signal.site,
        time_window=signal.time_window,
        summary=signal.summary,
        metrics=signal.metrics,
        evidence_ids=signal.evidence_ids,
        analysis_run_id=signal.analysis_run_id,
        explanation=signal.explanation,
    )
    row = site_columns(verified.site)
    row.update(
        {
            "signal_id": verified.signal_id,
            "detector_id": verified.detector_id.value,
            "detector_version": verified.detector_version.value,
            "signal_type": verified.signal_type.value,
            "window_start": dt_to_iso(verified.time_window.start),
            "window_end": dt_to_iso(verified.time_window.end),
            "summary": verified.summary,
            "metrics_json": dumps_structured(dict(verified.metrics)),
            "explanation_json": dumps_structured(dict(verified.explanation)),
            "analysis_run_id": verified.analysis_run_id,
        }
    )
    return row, verified.evidence_ids


def environmental_signal_from_parts(
    row: Mapping[str, Any],
    evidence_ids: Sequence[str],
) -> EnvironmentalSignal:
    try:
        return EnvironmentalSignal.create(
            signal_id=str(row["signal_id"]),
            detector_id=DetectorId(str(row["detector_id"])),
            detector_version=DetectorVersion(str(row["detector_version"])),
            signal_type=SignalType(str(row["signal_type"])),
            site=site_from_columns(row),
            time_window=TimeWindow(
                start=dt_from_iso(str(row["window_start"])),
                end=dt_from_iso(str(row["window_end"])),
            ),
            summary=str(row["summary"]),
            metrics=loads_structured(str(row["metrics_json"])),
            evidence_ids=tuple(str(eid) for eid in evidence_ids),
            analysis_run_id=str(row["analysis_run_id"]),
            explanation=loads_structured(str(row["explanation_json"])),
        )
    except SerializationFailure:
        raise
    except Exception as exc:
        raise SerializationFailure(
            f"failed to map environmental_signal {row.get('signal_id')}"
        ) from exc


def analysis_run_to_row(run: AnalysisRun) -> dict[str, Any]:
    return {
        "run_id": run.run_id,
        "started_at": dt_to_iso(run.started_at),
        "finished_at": dt_to_iso(run.finished_at) if run.finished_at else None,
        "status": run.status.value,
        "snapshot_hash": run.snapshot_hash,
        "detector_set_version": run.detector_set_version,
        "parameters_hash": run.parameters_hash,
        "error": run.error,
        "site_id": run.site_id,
        "window_start": dt_to_iso(run.time_window.start),
        "window_end": dt_to_iso(run.time_window.end),
    }


def analysis_run_from_parts(
    row: Mapping[str, Any],
    signals_produced: Sequence[str],
) -> AnalysisRun:
    try:
        from datetime import timedelta

        finished = row["finished_at"]
        site_id = str(row["site_id"]) if "site_id" in row.keys() else ""
        window_start = row["window_start"] if "window_start" in row.keys() else None
        window_end = row["window_end"] if "window_end" in row.keys() else None
        if window_start and window_end:
            time_window = TimeWindow(
                start=dt_from_iso(str(window_start)),
                end=dt_from_iso(str(window_end)),
            )
        else:
            # Pre-A6 rows: placeholder open interval; brief may derive from signals.
            started = dt_from_iso(str(row["started_at"]))
            time_window = TimeWindow(
                start=started,
                end=started + timedelta(microseconds=1),
            )
        return AnalysisRun(
            run_id=str(row["run_id"]),
            started_at=dt_from_iso(str(row["started_at"])),
            finished_at=dt_from_iso(str(finished)) if finished else None,
            status=AnalysisRunStatus(str(row["status"])),
            snapshot_hash=str(row["snapshot_hash"]),
            detector_set_version=str(row["detector_set_version"]),
            parameters_hash=str(row["parameters_hash"]),
            site_id=site_id or "unknown",
            time_window=time_window,
            signals_produced=tuple(str(sid) for sid in signals_produced),
            error=row["error"],
        )
    except SerializationFailure:
        raise
    except Exception as exc:
        raise SerializationFailure(
            f"failed to map analysis_run {row.get('run_id')}"
        ) from exc


def investigation_case_to_row(case: InvestigationCase) -> dict[str, Any]:
    row = site_columns(case.site)
    row.update(
        {
            "case_id": case.case_id,
            "window_start": dt_to_iso(case.window.start),
            "window_end": dt_to_iso(case.window.end),
            "analysis_run_id": case.analysis_run_id,
            "reproducibility_ref": case.reproducibility_ref,
            "opened_at": dt_to_iso(case.opened_at),
            "state": case.state.value,
        }
    )
    return row


def investigation_case_from_parts(
    row: Mapping[str, Any],
    signal_ids: Sequence[str],
    decision_ids: Sequence[str],
) -> InvestigationCase:
    try:
        return InvestigationCase(
            case_id=str(row["case_id"]),
            site=site_from_columns(row),
            window=TimeWindow(
                start=dt_from_iso(str(row["window_start"])),
                end=dt_from_iso(str(row["window_end"])),
            ),
            analysis_run_id=str(row["analysis_run_id"]),
            signal_ids=tuple(str(sid) for sid in signal_ids),
            reproducibility_ref=str(row["reproducibility_ref"]),
            opened_at=dt_from_iso(str(row["opened_at"])),
            state=CaseState(str(row["state"])),
            decision_ids=tuple(str(did) for did in decision_ids),
        )
    except SerializationFailure:
        raise
    except Exception as exc:
        raise SerializationFailure(
            f"failed to map investigation_case {row.get('case_id')}"
        ) from exc


def human_decision_to_parts(
    decision: HumanDecision,
) -> tuple[dict[str, Any], tuple[str, ...]]:
    # Re-enforce AI cannot author decisions on save/load.
    verified = HumanDecision.create(
        decision_id=decision.decision_id,
        case_id=decision.case_id,
        actor=decision.actor,
        decided_at=decision.decided_at,
        decision_code=decision.decision_code,
        rationale=decision.rationale,
        linked_signal_ids=decision.linked_signal_ids,
    )
    row = {
        "decision_id": verified.decision_id,
        "case_id": verified.case_id,
        "actor_type": verified.actor.actor_type.value,
        "actor_id": verified.actor.actor_id,
        "decided_at": dt_to_iso(verified.decided_at),
        "decision_code": verified.decision_code.value,
        "rationale": verified.rationale,
    }
    return row, verified.linked_signal_ids


def human_decision_from_parts(
    row: Mapping[str, Any],
    linked_signal_ids: Sequence[str],
) -> HumanDecision:
    try:
        return HumanDecision.create(
            decision_id=str(row["decision_id"]),
            case_id=str(row["case_id"]),
            actor=Actor(ActorType(str(row["actor_type"])), str(row["actor_id"])),
            decided_at=dt_from_iso(str(row["decided_at"])),
            decision_code=DecisionCode(str(row["decision_code"])),
            rationale=str(row["rationale"]),
            linked_signal_ids=tuple(str(sid) for sid in linked_signal_ids),
        )
    except SerializationFailure:
        raise
    except Exception as exc:
        raise SerializationFailure(
            f"failed to map human_decision {row.get('decision_id')}"
        ) from exc
