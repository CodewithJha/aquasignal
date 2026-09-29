"""P0.3 — end-to-end demo path over HTTP with Null AI (no seed script).

submit → validate → confirm → finalize → evidence → analysis → brief →
HumanDecision → optional AI advisory → FHIR.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.composition import build_services, reset_services, set_services
from app.flags.engine import DeterministicFlagEngine
from app.main import app
from tests.db import make_settings


@pytest.fixture
def client(tmp_path: Path):
    reset_services()
    services = build_services(
        settings=make_settings(tmp_path / "p0_http.sqlite3"),
        flag_engine=DeterministicFlagEngine(),
    )
    set_services(services)
    with TestClient(app) as c:
        yield c, services
    reset_services()


def _submit_and_finalize(c: TestClient, *, foam: str = "present") -> str:
    r = c.post(
        "/upload",
        data={"site": "coimbra", "foam": foam, "colour": "clear", "smell": "none"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    packet_id = r.headers["location"].rsplit("/", 1)[-1]
    assert c.post(f"/observation/{packet_id}/confirm", follow_redirects=False).status_code == 303
    fin = c.post(
        f"/observation/{packet_id}/finalize",
        data={"one_health_sentence": "Cited association — not a diagnosis."},
        follow_redirects=False,
    )
    assert fin.status_code == 303
    return packet_id


def _case_id_and_version(html: str) -> tuple[str, str]:
    case_id = re.search(r"/investigate/cases/(case_[0-9a-f]+)/decisions", html).group(1)
    version = re.search(r'name="expected_version" value="(\d+)"', html).group(1)
    return case_id, version


def test_ten_step_demo_path(client) -> None:
    c, services = client
    packet_id = _submit_and_finalize(c)
    other = _submit_and_finalize(c, foam="absent")

    # Unfinalized observation at the same site must not enter the analysis.
    draft = c.post(
        "/upload",
        data={"site": "coimbra", "foam": "abundant", "colour": "clear", "smell": "none"},
        follow_redirects=False,
    ).headers["location"].rsplit("/", 1)[-1]

    # Viewing the site never triggers analysis.
    assert "No analysis yet" in c.get("/investigate/sites/coimbra").text
    assert services.brief.list_analyses_for_site("coimbra") == []

    r = c.post("/investigate/sites/coimbra/analyze", follow_redirects=False)
    assert r.status_code == 303
    run_url = r.headers["location"]
    run_id = run_url.rsplit("/", 1)[-1]

    brief = c.get(run_url)
    assert brief.status_code == 200
    assert packet_id in brief.text and other in brief.text
    assert draft not in brief.text
    assert "ConfirmGate finalized observation" in brief.text
    assert "SYNTHETIC FIXTURE" not in brief.text
    assert "AI advisory: disabled. Deterministic analysis is complete without it." in brief.text
    assert "AI: null" not in brief.text
    assert "Open investigation case" in brief.text

    assert c.post(f"/investigate/analyses/{run_id}/cases", follow_redirects=False).status_code == 303
    page = c.get(run_url).text
    case_id, version = _case_id_and_version(page)
    assert "No human decisions recorded yet." in page

    d = c.post(
        f"/investigate/cases/{case_id}/decisions",
        data={
            "decision_code": "request_more_evidence",
            "rationale": "Conflicting foam reports; ask for a repeat visit.",
            "expected_version": version,
        },
        follow_redirects=False,
    )
    assert d.status_code == 303
    after = c.get(run_url).text
    assert "request_more_evidence" in after
    assert "Conflicting foam reports; ask for a repeat visit." in after
    assert "UNDER_REVIEW" in after

    api = c.get(f"/api/analyses/{run_id}").json()
    assert api["cases"][0]["decisions"][0]["actor"]["type"] == "reviewer"
    assert api["ai_advisory"]["available"] is False

    bundle = c.get(f"/fhir/bundle?packet_id={packet_id}")
    assert bundle.status_code == 200
    for entry in bundle.json()["entry"]:
        if entry["resource"]["resourceType"] == "Observation":
            assert entry["resource"]["status"] == "final"
    assert c.get(f"/fhir/bundle?packet_id={draft}").status_code == 409


def test_analyze_without_finalized_shows_error(client) -> None:
    c, _ = client
    r = c.post("/investigate/sites/oslo/analyze", follow_redirects=False)
    assert r.status_code == 409
    assert "no FINALIZED observations" in r.text


def test_analyze_unknown_site_rejected(client) -> None:
    c, _ = client
    assert c.post("/investigate/sites/atlantis/analyze").status_code == 400


def test_decision_form_errors(client) -> None:
    c, _ = client
    _submit_and_finalize(c)
    run_url = c.post("/investigate/sites/coimbra/analyze", follow_redirects=False).headers["location"]
    run_id = run_url.rsplit("/", 1)[-1]
    c.post(f"/investigate/analyses/{run_id}/cases")
    case_id, version = _case_id_and_version(c.get(run_url).text)

    bad_code = c.post(
        f"/investigate/cases/{case_id}/decisions",
        data={"decision_code": "water_safe", "rationale": "x", "expected_version": version},
    )
    assert bad_code.status_code == 400
    no_rationale = c.post(
        f"/investigate/cases/{case_id}/decisions",
        data={"decision_code": "note", "rationale": "", "expected_version": version},
    )
    assert no_rationale.status_code == 400
    no_version = c.post(
        f"/investigate/cases/{case_id}/decisions",
        data={"decision_code": "note", "rationale": "x"},
    )
    assert no_version.status_code == 400

    ok = c.post(
        f"/investigate/cases/{case_id}/decisions",
        data={"decision_code": "dismiss", "rationale": "Not actionable.", "expected_version": version},
        follow_redirects=False,
    )
    assert ok.status_code == 303
    duplicate = c.post(
        f"/investigate/cases/{case_id}/decisions",
        data={"decision_code": "dismiss", "rationale": "Not actionable.", "expected_version": version},
    )
    assert duplicate.status_code == 409
    missing = c.post(
        "/investigate/cases/case_nope/decisions",
        data={"decision_code": "note", "rationale": "x", "expected_version": "1"},
    )
    assert missing.status_code == 404
    final = c.get(run_url).text
    assert "DISMISSED" in final
    assert final.count("Not actionable.") == 1
    assert "Record human decision" not in final
