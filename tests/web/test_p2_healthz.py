"""P2 — /healthz liveness endpoint for containers / PaaS."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.web.health_routes as health_routes
from app.composition import build_services, reset_services, set_services
from app.flags.engine import DeterministicFlagEngine
from app.main import app
from app.persistence.config import DatabaseSettings
from app.persistence.factory import database_reachable


@pytest.fixture
def client(tmp_path: Path):
    reset_services()
    set_services(
        build_services(
            settings=DatabaseSettings(sqlite_path=tmp_path / "health.sqlite3"),
            flag_engine=DeterministicFlagEngine(),
        )
    )
    with TestClient(app) as c:
        yield c
    reset_services()


def test_healthz_ok_with_fresh_db(client: TestClient) -> None:
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "database": "ok"}


def test_healthz_does_not_leak_config(client: TestClient) -> None:
    body = client.get("/healthz").text.lower()
    for secret_ish in ("sqlite3", "/", "api_key", "model"):
        assert secret_ish not in body


def test_healthz_503_when_db_unreachable(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(health_routes, "check_database", lambda: False)
    r = client.get("/healthz")
    assert r.status_code == 503
    assert r.json() == {"status": "degraded", "database": "unreachable"}


def test_database_reachable_false_for_unopenable_path(tmp_path: Path) -> None:
    blocker = tmp_path / "not_a_dir"
    blocker.write_text("file, not a directory")
    assert database_reachable(blocker / "db.sqlite3") is False
    assert database_reachable(tmp_path / "ok.sqlite3") is True
