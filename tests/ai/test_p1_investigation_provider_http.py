"""P1.3 — OptionalProviderInvestigationCopilot over mocked HTTP (no live key)."""

from __future__ import annotations

import dataclasses
import json
from typing import Any

import httpx
import pytest

from app.ai.investigation_port import (
    CopilotEvidenceRef,
    CopilotSignalRef,
    InvestigationBriefInput,
)
from app.ai.investigation_provider import OptionalProviderInvestigationCopilot
from app.ai.investigation_validate import hash_investigation_brief

API_KEY = "test-key-not-for-prod"


def _brief() -> InvestigationBriefInput:
    return InvestigationBriefInput(
        run_id="run_abc123",
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
                signal_id="sig_known",
                signal_type="temporal_shift",
                summary="Possible temporal shift in foam reports (hypothesis).",
                is_insufficient=False,
                evidence_ids=("fix_a_01", "fix_a_02"),
            ),
        ),
        evidence=(
            CopilotEvidenceRef("fix_a_01", "fixture", True, {"foam": "absent"}),
            CopilotEvidenceRef("fix_a_02", "fixture", True, {"foam": "abundant"}),
        ),
        contradiction_messages=("foam absent vs abundant",),
        supports_messages=(),
        system_analysis_note="SYSTEM ANALYSIS — deterministic detectors.",
    )


class _Resp:
    def __init__(self, status: int = 200, content: Any = None, body: Any = None) -> None:
        self.status_code = status
        self._content = content
        self._body = body

    def json(self) -> Any:
        if self._body is not None:
            return self._body
        return {"choices": [{"message": {"content": self._content}}]}


def _valid_payload(**overrides: Any) -> dict[str, Any]:
    payload = {
        "summary": "One temporal signal and one conflict between fix_a_01 and fix_a_02.",
        "signal_explanations": [
            {"signal_id": "sig_known", "explanation": "Foam reports moved from absent to abundant."}
        ],
        "missing_evidence": ["repeat_protocol_observation"],
        "limitations": ["Confidence is low with two observations.", "No alert needed from this brief."],
    }
    payload.update(overrides)
    return payload


def _copilot(post) -> OptionalProviderInvestigationCopilot:
    return OptionalProviderInvestigationCopilot(
        api_key=API_KEY, model="test-model", timeout_seconds=2.0, http_post=post
    )


def _advise(response_or_exc):
    calls: list[dict[str, Any]] = []

    def post(url, json=None, headers=None, timeout=None):
        calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        if isinstance(response_or_exc, Exception):
            raise response_or_exc
        return response_or_exc

    return _copilot(post).advise(_brief()), calls


def test_valid_advisory_and_request_contract() -> None:
    out, calls = _advise(_Resp(content=json.dumps(_valid_payload())))
    assert out.available is True
    assert out.validation_status == "valid"
    assert out.input_brief_hash == hash_investigation_brief(_brief())
    assert [s.signal_id for s in out.signal_explanations] == ["sig_known"]
    assert len(calls) == 1  # no retries
    call = calls[0]
    assert call["timeout"] == 2.0
    assert call["url"].endswith("/chat/completions")
    assert call["headers"]["Authorization"] == f"Bearer {API_KEY}"
    assert API_KEY not in json.dumps(call["json"])
    user = json.loads(call["json"]["messages"][1]["content"])
    assert user["input_brief_hash"] == out.input_brief_hash
    assert user["brief"]["run_id"] == "run_abc123"


def test_input_is_immutable() -> None:
    brief = _brief()
    with pytest.raises(dataclasses.FrozenInstanceError):
        brief.signal_count = 99  # type: ignore[misc]


@pytest.mark.parametrize(
    "response, status",
    [
        (_Resp(content="not json at all"), "unavailable"),
        (_Resp(content="[1, 2, 3]"), "unavailable"),
        (_Resp(body={"unexpected": True}), "unavailable"),
        (_Resp(status=500, content="{}"), "unavailable"),
        (_Resp(status=429, content="{}"), "unavailable"),
    ],
)
def test_malformed_or_http_error_is_unavailable(response, status) -> None:
    out, calls = _advise(response)
    assert out.available is False
    assert out.validation_status == status
    assert out.summary == ""
    assert len(calls) == 1


def test_timeout() -> None:
    out, calls = _advise(httpx.ReadTimeout("read timed out"))
    assert out.available is False
    assert out.validation_status == "timeout"
    assert len(calls) == 1


def test_connection_unavailable() -> None:
    out, _ = _advise(httpx.ConnectError("connection refused"))
    assert out.available is False
    assert out.validation_status == "unavailable"


@pytest.mark.parametrize(
    "payload, note",
    [
        (_valid_payload(signal_explanations="not-a-list"), "malformed"),
        (_valid_payload(missing_evidence="human_review"), "malformed"),
        (
            _valid_payload(signal_explanations=[{"signal_id": "sig_invented", "explanation": "x"}]),
            "unknown signal_id",
        ),
        (_valid_payload(missing_evidence=["lab_pathogen_panel"]), "invalid missing_evidence"),
        (_valid_payload(summary="Readings suggest sewage overflow upstream."), "forbidden"),
        (_valid_payload(limitations=["E. coli levels may be elevated."]), "forbidden"),
        (_valid_payload(input_brief_hash="0" * 64), "input_brief_hash"),
        (_valid_payload(summary="See evidence fix_zz_99 for the change."), "unknown ids"),
        (_valid_payload(summary="Compare with run_other123."), "unknown ids"),
        ({"summary": "", "signal_explanations": [], "missing_evidence": [], "limitations": []}, "empty"),
    ],
)
def test_structural_and_claim_rejections(payload, note) -> None:
    out, _ = _advise(_Resp(content=json.dumps(payload)))
    assert out.available is False
    assert out.validation_status == "rejected"
    assert note in (out.notes or "")
    assert out.summary == "" and out.signal_explanations == []


def test_matching_echoed_brief_hash_is_accepted() -> None:
    payload = _valid_payload(input_brief_hash=hash_investigation_brief(_brief()))
    out, _ = _advise(_Resp(content=json.dumps(payload)))
    assert out.available is True
