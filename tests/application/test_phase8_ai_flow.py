"""Phase 8 application flow — human accept/decline, AI unavailable, FHIR isolation."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.ai.fake import FakeAiAssist
from app.ai.null import NullAiAssist
from app.application.citizen_flow import CitizenFlowService
from app.composition import build_services
from app.domain.enums import ActorType, FieldSource, WorkflowState
from app.domain.errors import UnauthorizedDomainAction
from app.domain.sites import get_site
from app.domain.value_objects import Actor, FieldValue
from app.fhir.errors import FhirExportRefused
from app.fhir.exporter import export_bundle_with_meta
from app.fhir.validator import NullFhirValidator
from app.flags.engine import DeterministicFlagEngine
from tests.db import make_settings


def _services(tmp_path: Path, ai) -> CitizenFlowService:
    settings = make_settings(tmp_path / "phase8.sqlite3")
    return build_services(
        settings=settings,
        flag_engine=DeterministicFlagEngine(),
        ai=ai,
        fhir_validator=NullFhirValidator(),
    ).flow


@pytest.fixture
def null_flow(tmp_path: Path) -> CitizenFlowService:
    return _services(tmp_path, NullAiAssist())


@pytest.fixture
def fake_flow(tmp_path: Path) -> CitizenFlowService:
    return _services(
        tmp_path,
        FakeAiAssist(preset={"foam": "absent", "colour": "clear", "smell": "none"}),
    )


@pytest.fixture
def failing_ai_flow(tmp_path: Path) -> CitizenFlowService:
    return _services(tmp_path, FakeAiAssist(fail=True))


def _complete_fields() -> dict[str, FieldValue]:
    return {
        "foam": FieldValue(code="foam", value="present"),
        "colour": FieldValue(code="colour", value="clear"),
        "smell": FieldValue(code="smell", value="none"),
    }


def test_ai_suggests_fields_unchanged(fake_flow: CitizenFlowService) -> None:
    site = get_site("coimbra")
    fields = {
        "colour": FieldValue(code="colour", value="brown"),
        "smell": FieldValue(code="smell", value="mild"),
    }
    record = fake_flow.submit(site=site, fields=fields)
    packet = record.packet
    assert "foam" not in packet.fields
    assert "foam" in packet.suggestions
    assert packet.workflow_state == WorkflowState.FLAGGED


def test_human_accept_mutates_and_reruns_flags(fake_flow: CitizenFlowService) -> None:
    site = get_site("coimbra")
    fields = {
        "colour": FieldValue(code="colour", value="clear"),
        "smell": FieldValue(code="smell", value="none"),
    }
    record = fake_flow.submit(site=site, fields=fields)
    pid = record.packet.packet_id
    assert "foam" not in record.packet.fields

    accepted = fake_flow.accept_suggestion(pid, field="foam")
    assert accepted.packet.fields["foam"].value == "absent"
    assert accepted.packet.fields["foam"].source == FieldSource.AI_SUGGESTION_ACCEPTED
    assert accepted.packet.workflow_state == WorkflowState.FLAGGED


def test_human_decline_leaves_fields_unchanged(fake_flow: CitizenFlowService) -> None:
    site = get_site("coimbra")
    fields = {
        "colour": FieldValue(code="colour", value="clear"),
        "smell": FieldValue(code="smell", value="none"),
    }
    record = fake_flow.submit(site=site, fields=fields)
    pid = record.packet.packet_id
    before = {k: v.value for k, v in record.packet.fields.items()}

    declined = fake_flow.decline_suggestion(pid, field="foam")
    assert {k: v.value for k, v in declined.packet.fields.items()} == before
    assert "foam" not in declined.packet.suggestions
    events = fake_flow.list_provenance(pid)
    assert any(e.action == "suggestion.declined" for e in events)


def test_ai_unavailable_continues_to_fhir(failing_ai_flow: CitizenFlowService) -> None:
    site = get_site("coimbra")
    record = failing_ai_flow.submit(site=site, fields=_complete_fields())
    pid = record.packet.packet_id
    assert record.packet.workflow_state == WorkflowState.FLAGGED
    events = failing_ai_flow.list_provenance(pid)
    assert any(e.action == "ai.unavailable" for e in events)

    soft = [f for f in record.packet.flags if f.is_standing_soft_block]
    hard = [f for f in record.packet.flags if f.is_standing_hard_reject]
    assert not hard
    if soft:
        record = failing_ai_flow.correct(pid, fields=_complete_fields())

    confirmed = failing_ai_flow.confirm(pid)
    assert confirmed.packet.workflow_state == WorkflowState.CONFIRMED
    finalized = failing_ai_flow.finalize(pid)
    assert finalized.packet.workflow_state == WorkflowState.FINALIZED
    _, result = failing_ai_flow.export_fhir(pid)
    assert result.bundle["resourceType"] == "Bundle"
    for entry in result.bundle.get("entry") or []:
        res = entry.get("resource") or {}
        if res.get("resourceType") == "Observation":
            assert res.get("status") == "final"


def test_ai_assisted_path_to_fhir(fake_flow: CitizenFlowService) -> None:
    site = get_site("benevento")
    fields = {
        "colour": FieldValue(code="colour", value="clear"),
        "smell": FieldValue(code="smell", value="none"),
    }
    record = fake_flow.submit(site=site, fields=fields)
    pid = record.packet.packet_id
    fake_flow.accept_suggestion(pid, field="foam")
    confirmed = fake_flow.confirm(pid)
    assert confirmed.packet.confirmation is not None
    foam = next(f for f in confirmed.packet.confirmation.fields if f.code == "foam")
    assert foam.source == FieldSource.AI_SUGGESTION_ACCEPTED
    finalized = fake_flow.finalize(pid)
    assert finalized.packet.workflow_state == WorkflowState.FINALIZED
    _, result = fake_flow.export_fhir(pid)
    assert result.bundle["resourceType"] == "Bundle"


def test_confirm_without_accepting_keeps_suggestion_out_of_fields(
    tmp_path: Path,
) -> None:
    flow = _services(tmp_path, FakeAiAssist(preset={"macrophytes": "p"}))
    site = get_site("toulouse")
    record = flow.submit(site=site, fields=_complete_fields())
    pid = record.packet.packet_id
    assert "macrophytes" in record.packet.suggestions
    assert "macrophytes" not in record.packet.fields

    confirmed = flow.confirm(pid)
    codes = {f.code for f in confirmed.packet.confirmation.fields}
    assert "macrophytes" not in codes


def test_ai_cannot_confirm_reject_finalize_or_export(
    null_flow: CitizenFlowService,
) -> None:
    site = get_site("oslo")
    record = null_flow.submit(site=site, fields=_complete_fields())
    packet = record.packet
    ai = Actor(ActorType.AI_PROVIDER, "fake-v1")
    with pytest.raises(UnauthorizedDomainAction):
        packet.confirm(actor=ai)
    with pytest.raises(UnauthorizedDomainAction):
        packet.finalize(actor=ai)
    with pytest.raises(UnauthorizedDomainAction):
        packet.reject(actor=ai, reason_code="other")
    with pytest.raises(FhirExportRefused):
        export_bundle_with_meta(packet, validator=NullFhirValidator())


def test_null_core_path_still_works(null_flow: CitizenFlowService) -> None:
    site = get_site("ghent")
    record = null_flow.submit(site=site, fields=_complete_fields())
    pid = record.packet.packet_id
    soft = [f for f in record.packet.flags if f.is_standing_soft_block]
    if soft:
        null_flow.correct(pid, fields=_complete_fields())
    null_flow.confirm(pid)
    null_flow.finalize(pid)
    _, result = null_flow.export_fhir(pid)
    assert result.bundle["resourceType"] == "Bundle"
