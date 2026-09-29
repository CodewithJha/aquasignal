"""FlagEngine orchestration, determinism, and safety tests."""

from __future__ import annotations

from app.domain.enums import ActorType, Severity
from app.domain.packet import ObservationPacket
from app.domain.value_objects import Actor, FieldValue
from app.flags.engine import DeterministicFlagEngine, FLAG_RULES_VERSION
from tests.flags.conftest import complete_packet, sensory_fields


def test_empty_packet_produces_completeness_and_fhir_flags(
    empty_packet: ObservationPacket, engine: DeterministicFlagEngine
) -> None:
    flags = engine.evaluate(empty_packet)
    codes = {f.code for f in flags}
    assert "COMPLETENESS_EMPTY" in codes
    assert "FHIR_MISSING_EFFECTIVE" in codes
    assert all(f.rule_version == FLAG_RULES_VERSION for f in flags)
    assert not hasattr(engine, "trust_score")
    assert not any("trust" in f.code.lower() for f in flags)
    assert not any("score" in f.rule_id.lower() for f in flags)


def test_valid_complete_packet_minimal_flags(
    coimbra_site, citizen, engine: DeterministicFlagEngine
) -> None:
    packet = complete_packet(coimbra_site, citizen)
    flags = engine.evaluate(packet)
    # Sensory complete + effective_at + location id → no soft completeness/fhir gaps
    assert not any(f.severity == Severity.HARD_REJECT for f in flags)
    soft_codes = {f.code for f in flags if f.severity == Severity.SOFT_BLOCK_FINALIZE}
    assert "COMPLETENESS_EMPTY" not in soft_codes
    assert "COMPLETENESS_REQUIRED" not in soft_codes
    assert "FHIR_MISSING_EFFECTIVE" not in soft_codes
    assert "FHIR_MISSING_LOCATION_ID" not in soft_codes


def test_multiple_violations_collected(
    empty_packet: ObservationPacket,
    citizen: Actor,
    engine: DeterministicFlagEngine,
) -> None:
    empty_packet.apply_suggestions(
        {"pathogen": "detected"},
        actor=Actor(ActorType.AI_PROVIDER, "null"),
    )
    empty_packet.set_notes("possible BMWP claim", actor=citizen)
    flags = engine.evaluate(empty_packet)
    families = {f.rule_id.split(".")[0] for f in flags}
    assert "completeness" in families
    assert "nonclaim" in families
    assert "fhir_readiness" in families
    assert len(flags) >= 3


def test_deterministic_ordering_and_repeat(
    empty_packet: ObservationPacket, engine: DeterministicFlagEngine
) -> None:
    a = engine.evaluate(empty_packet)
    b = engine.evaluate(empty_packet)
    assert [(f.flag_id, f.rule_id, f.code, f.severity) for f in a] == [
        (f.flag_id, f.rule_id, f.code, f.severity) for f in b
    ]
    # Severity order: hard → soft → warn
    severities = [f.severity for f in a]
    rank = {
        Severity.HARD_REJECT: 0,
        Severity.SOFT_BLOCK_FINALIZE: 1,
        Severity.WARN: 2,
    }
    assert severities == sorted(severities, key=lambda s: rank[s])


def test_ruleset_version(engine: DeterministicFlagEngine) -> None:
    assert engine.version == FLAG_RULES_VERSION
    assert engine.version == "0.1.0"


def test_revalidation_after_edit(
    empty_packet: ObservationPacket,
    citizen: Actor,
    system: Actor,
    engine: DeterministicFlagEngine,
) -> None:
    first = engine.evaluate(empty_packet)
    assert any(f.code == "COMPLETENESS_EMPTY" for f in first)
    empty_packet.apply_flags(first, actor=system, rule_engine_version=engine.version)

    for fv in sensory_fields():
        empty_packet.set_field(fv, actor=citizen)
    # Stale flags cleared on FLAGGED edit
    assert empty_packet.flags == ()

    second = engine.evaluate(empty_packet)
    assert not any(f.code == "COMPLETENESS_EMPTY" for f in second)
    assert not any(f.rule_id == "completeness.no_protocol_fields" for f in second)


def test_engine_does_not_mutate_workflow(
    empty_packet: ObservationPacket, engine: DeterministicFlagEngine
) -> None:
    from app.domain.enums import WorkflowState

    assert empty_packet.workflow_state == WorkflowState.RECEIVED
    engine.evaluate(empty_packet)
    assert empty_packet.workflow_state == WorkflowState.RECEIVED
    assert empty_packet.flags == ()


def test_invalid_vocab_hard_reject(
    empty_packet: ObservationPacket, citizen: Actor, engine: DeterministicFlagEngine
) -> None:
    empty_packet.set_field(FieldValue(code="foam", value="sparkly"), actor=citizen)
    flags = engine.evaluate(empty_packet)
    assert any(
        f.rule_id.startswith("vocabulary.invalid_value")
        and f.severity == Severity.HARD_REJECT
        for f in flags
    )
