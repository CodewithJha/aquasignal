"""Phase 6 integration — submit → flag → edit → revalidate → confirm → finalize → FHIR."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.application.citizen_flow import CitizenFlowError, CitizenFlowService
from app.ai.null import NullAiAssist
from app.composition import build_services, reset_services, set_services
from app.domain.enums import WorkflowState
from app.domain.sites import get_site
from app.domain.value_objects import FieldValue
from app.fhir.validator import NullFhirValidator
from app.flags.engine import DeterministicFlagEngine
from app.web.forms import parse_submission
from tests.db import make_settings

FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "demo_coimbra_sensory.json"
)


@pytest.fixture
def services(tmp_path: Path):
    reset_services()
    settings = make_settings(tmp_path / "phase6.sqlite3")
    built = build_services(
        settings=settings,
        flag_engine=DeterministicFlagEngine(),
        ai=NullAiAssist(),
        fhir_validator=NullFhirValidator(),
    )
    set_services(built)
    yield built
    reset_services()


@pytest.fixture
def flow(services) -> CitizenFlowService:
    return services.flow


def _fields_from_fixture() -> dict[str, FieldValue]:
    data = json.loads(FIXTURE.read_text())
    parsed = parse_submission({"site": data["site_id"], **data["fields"]})
    assert parsed.ok
    return parsed.fields


def test_full_citizen_path_null_ai_null_validator(flow: CitizenFlowService) -> None:
    data = json.loads(FIXTURE.read_text())
    site = get_site(data["site_id"])
    record = flow.submit(site=site, fields=_fields_from_fixture(), notes=data["notes"])
    packet = record.packet
    assert packet.workflow_state == WorkflowState.FLAGGED
    assert isinstance(flow.observation.flag_engine, DeterministicFlagEngine)

    # Incomplete edit → soft blocks; same packet_id
    incomplete = {
        "foam": FieldValue(code="foam", value="present"),
    }
    corrected = flow.correct(packet.packet_id, fields=incomplete)
    assert corrected.packet.packet_id == packet.packet_id
    assert corrected.packet.workflow_state == WorkflowState.FLAGGED
    assert any(
        f.severity.value == "soft_block_finalize" for f in corrected.packet.flags
    )

    # Revalidate to complete sensory triad
    complete = flow.correct(packet.packet_id, fields=_fields_from_fixture())
    soft = [f for f in complete.packet.flags if f.is_standing_soft_block]
    hard = [f for f in complete.packet.flags if f.is_standing_hard_reject]
    assert not soft and not hard

    confirmed = flow.confirm(packet.packet_id)
    assert confirmed.packet.workflow_state == WorkflowState.CONFIRMED
    assert confirmed.packet.confirmation is not None
    snap_hash = confirmed.packet.confirmation.content_hash

    # CONFIRMED cannot export
    with pytest.raises(CitizenFlowError) as refused:
        flow.export_fhir(packet.packet_id)
    assert refused.value.code == "export_not_finalized"

    finalized = flow.finalize(
        packet.packet_id,
        one_health_sentence=data["one_health_sentence"],
    )
    assert finalized.packet.workflow_state == WorkflowState.FINALIZED

    _rec, result = flow.export_fhir(packet.packet_id)
    assert result.bundle_hash
    assert result.mapper_version
    meta = flow.export_meta(result)
    assert meta["validation_status"] == "not_run"
    assert "not an OAH IG validator pass" in meta["validation_note"]
    for entry in result.bundle["entry"]:
        res = entry["resource"]
        if res["resourceType"] == "Observation":
            assert res["status"] == "final"
            assert res["status"] != "preliminary"

    # Snapshot authority survives
    assert _rec.packet.confirmation is not None
    assert _rec.packet.confirmation.content_hash == snap_hash


def test_unsupported_form_values_rejected(flow: CitizenFlowService) -> None:
    parsed = parse_submission({"site": "coimbra", "foam": "not-a-real-value"})
    assert not parsed.ok


def test_persistence_survives_reload(services, flow: CitizenFlowService, tmp_path: Path) -> None:
    site = get_site("coimbra")
    record = flow.submit(site=site, fields=_fields_from_fixture())
    pid = record.packet.packet_id
    flow.confirm(pid)
    flow.finalize(pid)

    # New service graph on same DB file
    rebuilt = build_services(
        settings=services.settings,
        flag_engine=DeterministicFlagEngine(),
        ai=NullAiAssist(),
        fhir_validator=NullFhirValidator(),
    )
    loaded = rebuilt.flow.get(pid).packet
    assert loaded.workflow_state == WorkflowState.FINALIZED
    assert loaded.confirmation is not None
    _r, result = rebuilt.flow.export_fhir(pid)
    assert result.bundle["resourceType"] == "Bundle"


def test_composition_injects_deterministic_not_null(services) -> None:
    assert type(services.flag_engine).__name__ == "DeterministicFlagEngine"
    assert type(services.observation.flag_engine).__name__ == "DeterministicFlagEngine"
