"""HTTP smoke for Phase 6 citizen path (TestClient — not full browser E2E).

Browser E2E skipped: no Playwright/Selenium justified in-repo yet; integration
covers domain path. This smoke checks redirects and HTML authority copy.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.composition import build_services, reset_services, set_services
from app.flags.engine import DeterministicFlagEngine
from app.main import app
from app.persistence.config import DatabaseSettings


@pytest.fixture
def client(tmp_path: Path):
    reset_services()
    services = build_services(
        settings=DatabaseSettings(sqlite_path=tmp_path / "http.sqlite3"),
        flag_engine=DeterministicFlagEngine(),
    )
    set_services(services)
    with TestClient(app) as c:
        yield c
    reset_services()


def test_upload_get_has_human_labels_not_fhir_jargon(client: TestClient) -> None:
    r = client.get("/upload")
    assert r.status_code == 200
    assert "Foam on the water" in r.text
    assert "TemporaryOahSystem" not in r.text
    assert "Diagnos" not in r.text or "does not diagnose" in r.text


def test_submit_correct_confirm_finalize_fhir_http(client: TestClient) -> None:
    r = client.post(
        "/upload",
        data={
            "site": "coimbra",
            "foam": "present",
            "colour": "clear",
            "smell": "none",
            "notes": "http smoke",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    loc = r.headers["location"]
    assert loc.startswith("/observation/")
    packet_id = loc.rsplit("/", 1)[-1]

    page = client.get(loc)
    assert page.status_code == 200
    assert "Needs correction" not in page.text or "Confirm observation" in page.text
    assert "DeterministicFlagEngine" in page.text
    assert "Confirm" in page.text and "Finalize" in page.text

    conf = client.post(f"/observation/{packet_id}/confirm", follow_redirects=False)
    assert conf.status_code == 303

    # CONFIRMED cannot get bundle
    refused = client.get(f"/fhir/bundle?packet_id={packet_id}")
    assert refused.status_code == 409

    fin = client.post(
        f"/observation/{packet_id}/finalize",
        data={"one_health_sentence": "Cited association — not a diagnosis."},
        follow_redirects=False,
    )
    assert fin.status_code == 303
    assert "fhir" in fin.headers["location"]

    fhir = client.get(f"/fhir?packet_id={packet_id}")
    assert fhir.status_code == 200
    assert "not_run" in fhir.text or "NullFhirValidator" in fhir.text
    assert "validator–green" in fhir.text or "validator" in fhir.text.lower()

    bundle = client.get(f"/fhir/bundle?packet_id={packet_id}")
    assert bundle.status_code == 200
    body = bundle.json()
    assert body["resourceType"] == "Bundle"
    for entry in body["entry"]:
        if entry["resource"]["resourceType"] == "Observation":
            assert entry["resource"]["status"] == "final"


def test_review_is_worklist(client: TestClient) -> None:
    r = client.get("/review")
    assert r.status_code == 200
    assert "Reviewer worklist" in r.text
    assert "NEEDS_REVIEW" in r.text
