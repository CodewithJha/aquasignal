"""A5 HTTP / UI integration — investigation brief surfaces."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.composition import build_services, reset_services, set_services
from app.domain.signal.value_objects import TimeWindow
from app.domain.sites import get_site
from app.flags.engine import DeterministicFlagEngine
from app.main import app
from app.persistence.config import DatabaseSettings
from datetime import datetime, timezone
from tests.application.aquasignal.conftest import make_analysis_params
from tests.signals.fixture_loader import load_fixture

PROHIBITED = (
    "water is safe",
    "pollution detected",
    "pathogen present",
    "disease outbreak",
    "trust score",
    "confidence %",
    "healthy stream",
)


@pytest.fixture
def client(tmp_path: Path):
    reset_services()
    services = build_services(
        settings=DatabaseSettings(sqlite_path=tmp_path / "a5_http.sqlite3"),
        flag_engine=DeterministicFlagEngine(),
    )
    set_services(services)
    with TestClient(app) as c:
        yield c, services
    reset_services()


def _seed_coimbra(services) -> str:
    coimbra = get_site("coimbra")
    analysis_window = TimeWindow(
        start=datetime(2026, 6, 1, tzinfo=timezone.utc),
        end=datetime(2026, 9, 30, tzinfo=timezone.utc),
    )
    baseline = TimeWindow(
        start=datetime(2026, 6, 1, tzinfo=timezone.utc),
        end=datetime(2026, 8, 1, tzinfo=timezone.utc),
    )
    recent = TimeWindow(
        start=datetime(2026, 9, 1, tzinfo=timezone.utc),
        end=datetime(2026, 9, 30, tzinfo=timezone.utc),
    )
    params = make_analysis_params(coimbra, analysis_window, baseline, recent)
    fixtures = load_fixture("A_temporal_shift") + load_fixture("C_contradiction")
    outcome = services.analysis.analyze(
        site=coimbra,
        time_window=analysis_window,
        fixture_observations=fixtures,
        params=params,
    )
    return outcome.run.run_id


def test_investigate_index_and_empty_site(client) -> None:
    c, _services = client
    r = c.get("/investigate")
    assert r.status_code == 200
    assert "Site Investigation Brief" in r.text
    assert "Coimbra" in r.text
    for bad in PROHIBITED:
        assert bad.lower() not in r.text.lower()

    empty = c.get("/investigate/sites/coimbra")
    assert empty.status_code == 200
    assert "No analysis yet" in empty.text


def test_analysis_list_and_detail_render(client) -> None:
    c, services = client
    run_id = _seed_coimbra(services)

    listing = c.get("/investigate/sites/coimbra")
    assert listing.status_code == 200
    assert run_id in listing.text
    assert "SUCCEEDED" in listing.text
    assert "Detector set" in listing.text or "detector" in listing.text.lower()
    assert ">Good<" not in listing.text
    assert ">Bad<" not in listing.text
    assert ">Risk<" not in listing.text
    assert ">Healthy<" not in listing.text

    detail = c.get(f"/investigate/analyses/{run_id}")
    assert detail.status_code == 200
    body = detail.text
    assert "Investigation summary" in body
    assert "What we found" in body
    assert "Why?" in body
    assert "Detector signals" in body
    assert "Technical details" in body
    assert "Reproducibility" in body
    assert "SYNTHETIC FIXTURE" in body
    assert "SYSTEM ANALYSIS" in body
    assert "HUMAN REVIEW" in body or "HUMAN DECISION" in body
    assert "AI ADVISORY" in body or "AI advisory unavailable" in body
    assert "snapshot hash" in body.lower() or "Snapshot hash" in body
    assert "trust score" not in body.lower()
    assert "confidence %" not in body.lower()
    assert "water is safe" not in body.lower()
    assert "pollution detected" not in body.lower()
    assert "pathogen present" not in body.lower()
    # Temporal ordinal timeline when shift present
    assert "temporal" in body.lower() or "foam" in body.lower()


def test_api_ai_advisory_null_by_default(client) -> None:
    c, services = client
    run_id = _seed_coimbra(services)
    detail = c.get(f"/api/analyses/{run_id}")
    assert detail.status_code == 200
    advisory = detail.json()["ai_advisory"]
    assert advisory["available"] is False
    assert advisory["validation_status"] in {"null", "unavailable", "rejected"}
    assert "provenance" in advisory
    assert advisory["provenance"]["prompt_version"]


def test_api_endpoints_typed(client) -> None:
    c, services = client
    run_id = _seed_coimbra(services)

    listing = c.get("/api/sites/coimbra/analyses")
    assert listing.status_code == 200
    data = listing.json()
    assert data["site_id"] == "coimbra"
    assert any(a["run_id"] == run_id for a in data["analyses"])

    detail = c.get(f"/api/analyses/{run_id}")
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["run_id"] == run_id
    assert "counts" in payload
    assert "trust" not in str(payload).lower()
    assert payload["reproducibility"]["snapshot_hash"]

    signals = c.get(f"/api/analyses/{run_id}/signals")
    assert signals.status_code == 200
    assert "signals" in signals.json()

    evidence = c.get(f"/api/analyses/{run_id}/evidence")
    assert evidence.status_code == 200
    ev = evidence.json()["evidence"]
    assert ev
    assert any(e.get("is_synthetic") for e in ev)

    repro = c.get(f"/api/analyses/{run_id}/reproducibility")
    assert repro.status_code == 200
    assert repro.json()["reproducibility"]["parameters_hash"]


def test_missing_analysis_states(client) -> None:
    c, _services = client
    missing = c.get("/investigate/analyses/run_missing")
    assert missing.status_code == 404
    assert "No analysis" in missing.text or "not found" in missing.text.lower()

    api = c.get("/api/analyses/run_missing")
    assert api.status_code == 404


def test_confirmgate_nav_still_works(client) -> None:
    c, _services = client
    r = c.get("/upload")
    assert r.status_code == 200
    assert "Investigate" in r.text
