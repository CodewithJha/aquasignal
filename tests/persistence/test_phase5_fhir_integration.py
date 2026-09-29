"""Phase 5 end-to-end: create → flags → confirm → finalize → guard → map → hash → provenance → reload."""

from __future__ import annotations

from datetime import datetime, timezone

from app.application.audit import answer_hitl_audit_questions
from app.application.service import ObservationService
from app.domain.enums import WorkflowState
from app.domain.packet import ObservationPacket
from app.domain.value_objects import Actor, FieldValue, SiteRef
from app.fhir.exporter import export_bundle_with_meta
from app.fhir.versions import OAH_FHIR_MAPPER_VERSION, TEMPORARY_OAH_SYSTEM
from app.flags.engine import DeterministicFlagEngine


def test_phase5_full_pipeline_persists_bundle_hash(
    service: ObservationService,
    settings,
    coimbra: SiteRef,
    citizen: Actor,
    system: Actor,
) -> None:
    site = SiteRef(
        site_id=coimbra.site_id,
        city=coimbra.city,
        display_name=coimbra.display_name,
        fhir_location_identifier="coimbra",
        lat=40.2,
        lon=-8.4,
    )
    packet = ObservationPacket.create(
        site,
        author_actor_id=citizen.actor_id,
        submitter_display="Integration Citizen",
        effective_at=datetime(2026, 9, 21, 10, 0, tzinfo=timezone.utc),
    )
    for field in (
        FieldValue(code="foam", value="present"),
        FieldValue(code="colour", value="clear"),
        FieldValue(code="smell", value="none"),
        FieldValue(code="macrophytes", value="e"),
        FieldValue(code="riparian_vegetation", value="41-60-percent"),
        FieldValue(code="hydromorphology", value="p"),
    ):
        packet.set_field(field, actor=citizen)

    engine = DeterministicFlagEngine()
    flags = engine.evaluate(packet)
    packet.apply_flags(flags, actor=system, rule_engine_version=engine.version)
    for flag in list(packet.flags):
        if (flag.is_standing_soft_block or flag.is_standing_hard_reject) and flag.overridable:
            packet.override_flag(
                flag.flag_id, reason="phase5 integration", actor=citizen
            )

    packet.mark_awaiting_confirm(actor=system)
    packet.confirm(actor=citizen)
    packet.finalize(actor=system, one_health_sentence="Cited One Health association.")
    assert packet.workflow_state == WorkflowState.FINALIZED

    service.persist_new(packet)
    pid = packet.packet_id

    loaded = service.get(pid).packet
    result = export_bundle_with_meta(loaded)
    assert result.mapper_version == OAH_FHIR_MAPPER_VERSION
    assert result.bundle_hash
    assert result.bundle["type"] == "collection"
    obs_codes = {
        e["resource"]["code"]["coding"][0]["code"]
        for e in result.bundle["entry"]
        if e["resource"]["resourceType"] == "Observation"
    }
    assert obs_codes >= {"foam", "macrophytes", "riparianVegetation", "morophology"}
    for entry in result.bundle["entry"]:
        res = entry["resource"]
        if res["resourceType"] == "Observation":
            assert res["status"] == "final"
            assert res["code"]["coding"][0]["system"] == TEMPORARY_OAH_SYSTEM

    def _digest(p: ObservationPacket) -> None:
        p.record_fhir_export_digest(
            actor=system,
            bundle_hash=result.bundle_hash,
            mapper_version=result.mapper_version,
        )

    service.mutate(pid, _digest)

    answers = answer_hitl_audit_questions(service.list_provenance(pid))
    assert answers["6_exported_bundle_hash"] != "N/A"
    assert answers["6_exported_bundle_hash"]["bundle_bytes_hash"] == result.bundle_hash
    assert answers["7_rule_and_mapper_versions"]["mapper_version"] == OAH_FHIR_MAPPER_VERSION

    from app.persistence.factory import open_unit_of_work

    conn, factory = open_unit_of_work(settings)
    svc2 = ObservationService(factory)
    reloaded = svc2.get(pid).packet
    assert reloaded.workflow_state == WorkflowState.FINALIZED
    again = export_bundle_with_meta(reloaded)
    assert again.bundle_hash == result.bundle_hash
    conn.close()
