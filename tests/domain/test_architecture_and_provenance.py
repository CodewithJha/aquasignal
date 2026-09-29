"""Architectural and provenance-boundary contract tests."""

from __future__ import annotations

import ast
from pathlib import Path

from app.domain.enums import ActorType, WorkflowState
from app.domain.packet import ObservationPacket
from app.domain.provenance_port import ProvenanceIntent
from app.domain.value_objects import Actor
from tests.domain.conftest import foam_field, reach_confirmed


DOMAIN_ROOT = Path(__file__).resolve().parents[2] / "app" / "domain"


def _imports_in(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
            # also record app.* second segment when from app.X
            parts = node.module.split(".")
            if parts[0] == "app" and len(parts) > 1:
                names.add(f"app.{parts[1]}")
    return names


def test_domain_does_not_import_fastapi_fhir_ai_web_db() -> None:
    forbidden = {
        "fastapi",
        "starlette",
        "jinja2",
        "sqlalchemy",
        "sqlite3",
        "httpx",
        "requests",
        "openai",
        "app.fhir",
        "app.ai",
        "app.web",
        "app.flags",
        "app.provenance",
        "app.persistence",
        "app.application",
    }
    for py in DOMAIN_ROOT.rglob("*.py"):
        imports = _imports_in(py)
        offenders = imports & forbidden
        assert not offenders, f"{py.relative_to(DOMAIN_ROOT)} imports forbidden: {offenders}"


def test_provenance_intents_answer_hitl_shape(
    packet: ObservationPacket, system: Actor, citizen: Actor
) -> None:
    packet.set_field(foam_field(), actor=citizen)
    packet.apply_suggestions(
        {"foam": "absent"},
        actor=Actor(ActorType.AI_PROVIDER, "null"),
        model_id="null",
        prompt_version="0",
    )
    reach_confirmed(packet, system=system, citizen=citizen)
    packet.finalize(actor=system, one_health_sentence="cited association")

    intents = packet.drain_provenance_intents()
    actions = {i.action for i in intents}
    assert "packet.created" in actions
    assert "fields.set" in actions
    assert "suggestions.applied" in actions
    assert "human.confirmed" in actions
    assert "fhir.exported" in actions

    confirm = next(i for i in intents if i.action == "human.confirmed")
    assert confirm.actor.actor_type == ActorType.CITIZEN
    assert confirm.after and "confirmation_hash" in confirm.after

    ai = next(i for i in intents if i.action == "suggestions.applied")
    assert ai.model_id == "null"

    # Drain clears buffer; enough info without concrete store.
    assert packet.pending_provenance() == ()
    assert all(isinstance(i, ProvenanceIntent) for i in intents)
    assert all("actor_type" in i.to_audit_dict() for i in intents)


def test_finalize_sets_exportable(
    packet: ObservationPacket, system: Actor, citizen: Actor
) -> None:
    reach_confirmed(packet, system=system, citizen=citizen)
    assert packet.workflow_state == WorkflowState.CONFIRMED
    assert not packet.is_exportable
    packet.finalize(actor=system)
    assert packet.is_exportable
