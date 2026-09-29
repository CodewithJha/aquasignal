"""A6 — InvestigationCopilotPort offline suite (no live LLM)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.ai.config import AiSettings
from app.ai.errors import AiAssistTimeout, AiAssistUnavailable
from app.ai.factory import build_investigation_copilot
from app.ai.investigation_fake import FakeInvestigationCopilot
from app.ai.investigation_null import NullInvestigationCopilot
from app.ai.investigation_port import (
    CopilotEvidenceRef,
    CopilotSignalRef,
    InvestigationBriefInput,
)
from app.ai.investigation_validate import (
    contains_forbidden_claim,
    hash_investigation_brief,
    validate_advisory_brief,
)
from app.ai.prompts import INVESTIGATION_COPILOT_PROMPT_VERSION
from app.application.investigation_advisory import brief_to_copilot_input, safe_advise
from app.application.investigation_brief import (
    AnalysisBrief,
    EvidenceView,
    ReproducibilityView,
    SignalView,
    StanceCounts,
)


def _brief_input(*, signal_id: str = "sig_1") -> InvestigationBriefInput:
    return InvestigationBriefInput(
        run_id="run_test",
        site_id="coimbra",
        site_label="Coimbra, Portugal",
        status="SUCCEEDED",
        detector_set_version="detectors@0.1.0",
        evidence_count=2,
        signal_count=1,
        supporting=0,
        conflicting=1,
        insufficient=0,
        duplicates=0,
        no_signal_success=False,
        failed=False,
        signals=(
            CopilotSignalRef(
                signal_id=signal_id,
                signal_type="temporal_shift",
                summary="Possible temporal shift in foam reports (hypothesis).",
                is_insufficient=False,
                evidence_ids=("fx_1", "fx_2"),
            ),
        ),
        evidence=(
            CopilotEvidenceRef(
                evidence_id="fx_1",
                source_class="fixture",
                is_synthetic=True,
                fields={"foam": "absent"},
            ),
            CopilotEvidenceRef(
                evidence_id="fx_2",
                source_class="fixture",
                is_synthetic=True,
                fields={"foam": "abundant"},
            ),
        ),
        contradiction_messages=("Foam disagree within window",),
        supports_messages=(),
        system_analysis_note="SYSTEM ANALYSIS — deterministic detectors.",
    )


def test_null_copilot_unavailable() -> None:
    copilot = NullInvestigationCopilot()
    out = copilot.advise(_brief_input())
    assert out.available is False
    assert out.validation_status == "null"
    assert out.prompt_version == INVESTIGATION_COPILOT_PROMPT_VERSION
    assert out.input_brief_hash == hash_investigation_brief(_brief_input())
    assert out.signal_explanations == []


def test_fake_valid_advisory() -> None:
    out = FakeInvestigationCopilot(mode="valid").advise(_brief_input())
    assert out.available is True
    assert out.validation_status == "valid"
    assert out.signal_explanations[0].signal_id == "sig_1"
    assert "human_review" in out.missing_evidence or out.missing_evidence
    assert out.provider == "fake"
    assert not contains_forbidden_claim(out.summary)


def test_fake_rejects_invalid_signal_id() -> None:
    out = FakeInvestigationCopilot(mode="invalid_signal_id").advise(_brief_input())
    assert out.available is False
    assert out.validation_status == "rejected"
    assert "unknown signal_id" in (out.notes or "")


def test_fake_rejects_invalid_missing_category() -> None:
    out = FakeInvestigationCopilot(mode="invalid_missing").advise(_brief_input())
    assert out.available is False
    assert "invalid missing_evidence" in (out.notes or "")


def test_fake_rejects_forbidden_conclusion() -> None:
    out = FakeInvestigationCopilot(mode="forbidden").advise(_brief_input())
    assert out.available is False
    assert "forbidden" in (out.notes or "").lower()


def test_fake_malformed_json() -> None:
    out = FakeInvestigationCopilot(mode="malformed").advise(_brief_input())
    assert out.available is False
    assert out.validation_status == "rejected"


def test_fake_unavailable_and_timeout_raise() -> None:
    with pytest.raises(AiAssistUnavailable):
        FakeInvestigationCopilot(mode="unavailable").advise(_brief_input())
    with pytest.raises(AiAssistTimeout):
        FakeInvestigationCopilot(mode="timeout").advise(_brief_input())


def test_safe_advise_swallows_timeout() -> None:
    now = datetime(2026, 9, 22, tzinfo=timezone.utc)
    later = datetime(2026, 9, 23, tzinfo=timezone.utc)
    brief = AnalysisBrief(
        run_id="run_x",
        site_id="coimbra",
        site_label="Coimbra",
        city="Coimbra",
        status="SUCCEEDED",
        window_start=now,
        window_end=later,
        evidence_count=0,
        signal_count=0,
        detector_set_version="detectors@0.1.0",
        stance=StanceCounts(0, 0, 0, 0),
        evidence=(),
        signals=(),
        contradictions=(),
        insufficient_signals=(),
        supports_messages=(),
        reproducibility=ReproducibilityView(
            run_id="run_x",
            snapshot_id=None,
            snapshot_hash="a" * 64,
            parameters_hash="b" * 64,
            detector_set_version="detectors@0.1.0",
            status="SUCCEEDED",
            evidence_count=0,
            started_at=now,
            finished_at=later,
        ),
        run_history=(),
        cases=(),
        no_signal_success=True,
        failed=False,
        failure_message=None,
    )
    out = safe_advise(FakeInvestigationCopilot(mode="timeout"), brief)
    assert out.available is False
    assert out.validation_status == "timeout"


def test_factory_null_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AI_PROVIDER", raising=False)
    monkeypatch.delenv("AI_API_KEY", raising=False)
    copilot = build_investigation_copilot(AiSettings.from_env())
    assert isinstance(copilot, NullInvestigationCopilot)


def test_validate_rejects_invented_evidence_in_text_and_bad_ids() -> None:
    brief = _brief_input()
    rejected = validate_advisory_brief(
        {
            "summary": "Pathogen outbreak likely from contamination.",
            "signal_explanations": [],
            "missing_evidence": ["human_review"],
            "limitations": [],
        },
        brief=brief,
        provider="t",
        model="m",
    )
    assert rejected.available is False


def test_copilot_cannot_mutate_domain_input() -> None:
    inp = _brief_input()
    before = hash_investigation_brief(inp)
    FakeInvestigationCopilot(mode="valid").advise(inp)
    assert hash_investigation_brief(inp) == before
    assert inp.signals[0].signal_id == "sig_1"


def test_brief_to_copilot_input_is_immutable_subset() -> None:
    now = datetime(2026, 9, 22, tzinfo=timezone.utc)
    later = datetime(2026, 9, 23, tzinfo=timezone.utc)
    analysis = AnalysisBrief(
        run_id="run_y",
        site_id="coimbra",
        site_label="Coimbra",
        city="Coimbra",
        status="SUCCEEDED",
        window_start=now,
        window_end=later,
        evidence_count=1,
        signal_count=1,
        detector_set_version="detectors@0.1.0",
        stance=StanceCounts(0, 0, 1, 0),
        evidence=(
            EvidenceView(
                evidence_id="fx_a",
                source_class="fixture",
                source_label="SYNTHETIC",
                is_synthetic=True,
                observed_at=now,
                site_id="coimbra",
                site_label="Coimbra",
                fields={"foam": "absent"},
                confirmgate_observation_url=None,
                license_tag="fixture-owned-mit",
            ),
        ),
        signals=(
            SignalView(
                signal_id="sig_insuf",
                signal_type="insufficient_evidence",
                summary="Not enough points",
                explanation={},
                detector_id="temporal_baseline_shift",
                detector_version="1.0.0",
                window_start=now,
                window_end=later,
                evidence_ids=("fx_a",),
                evidence_count=1,
                metrics={},
                is_insufficient=True,
            ),
        ),
        contradictions=(),
        insufficient_signals=(),
        supports_messages=(),
        reproducibility=ReproducibilityView(
            run_id="run_y",
            snapshot_id="snap",
            snapshot_hash="c" * 64,
            parameters_hash="d" * 64,
            detector_set_version="detectors@0.1.0",
            status="SUCCEEDED",
            evidence_count=1,
            started_at=now,
            finished_at=later,
        ),
        run_history=(),
        cases=(),
        no_signal_success=False,
        failed=False,
        failure_message=None,
    )
    inp = brief_to_copilot_input(analysis)
    assert inp.known_signal_ids == frozenset({"sig_insuf"})
    assert "fx_a" in inp.known_evidence_ids
