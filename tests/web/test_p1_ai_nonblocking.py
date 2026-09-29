"""P1.2 — AI calls never block the event loop or fail submit / brief."""

from __future__ import annotations

import inspect
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.ai.investigation_provider import OptionalProviderInvestigationCopilot
from app.ai.provider import OptionalProviderAiAssist
from app.composition import build_services, reset_services, set_services
from app.domain.enums import WorkflowState
from app.flags.engine import DeterministicFlagEngine
from app.main import app
from tests.db import make_settings

FORM = {"site": "coimbra", "foam": "present", "colour": "clear", "smell": "none"}


def _client(tmp_path: Path, **overrides):
    reset_services()
    services = build_services(
        settings=make_settings(tmp_path / "ai_nb.sqlite3"),
        flag_engine=DeterministicFlagEngine(),
        **overrides,
    )
    set_services(services)
    return services


@pytest.fixture(autouse=True)
def _reset():
    yield
    reset_services()


def test_all_http_handlers_are_sync() -> None:
    async_routes = [
        r.path
        for r in app.routes
        if isinstance(r, APIRoute) and inspect.iscoroutinefunction(r.endpoint)
    ]
    assert async_routes == []


def test_hung_ai_does_not_block_other_requests(tmp_path: Path) -> None:
    release = threading.Event()
    entered = threading.Event()

    def hanging_post(*_a, **_k):
        entered.set()
        release.wait(timeout=10)
        raise httpx.ReadTimeout("simulated slow provider")

    _client(
        tmp_path,
        ai=OptionalProviderAiAssist(api_key="k", model="m", http_post=hanging_post),
    )
    with TestClient(app) as client, ThreadPoolExecutor(max_workers=2) as pool:
        submit = pool.submit(client.post, "/upload", data=FORM, follow_redirects=False)
        assert entered.wait(timeout=5)
        # The event loop is free while the AI call is stuck in a worker thread.
        other = pool.submit(client.get, "/investigate")
        assert other.result(timeout=5).status_code == 200
        release.set()
        assert submit.result(timeout=10).status_code == 303


def test_ai_timeout_does_not_fail_submit_or_mutate_domain(tmp_path: Path) -> None:
    calls: list[str] = []

    def timeout_post(*_a, **_k):
        calls.append("post")
        raise httpx.ReadTimeout("timed out")

    services = _client(
        tmp_path,
        ai=OptionalProviderAiAssist(api_key="k", model="m", http_post=timeout_post),
    )
    with TestClient(app) as client:
        r = client.post(
            "/upload",
            data={"site": "coimbra", "foam": "present", "colour": "", "smell": ""},
            follow_redirects=False,
        )
    assert r.status_code == 303
    packet_id = r.headers["location"].rsplit("/", 1)[-1]
    packet = services.flow.get(packet_id).packet
    assert packet.workflow_state is WorkflowState.FLAGGED
    assert packet.suggestions == {}
    # One enum call plus at most one flag-explain call before giving up.
    assert 1 <= len(calls) <= 2
    actions = [e.action for e in services.flow.list_provenance(packet_id)]
    assert "ai.unavailable" in actions


def test_copilot_timeout_does_not_break_brief(tmp_path: Path) -> None:
    def timeout_post(*_a, **_k):
        raise httpx.ReadTimeout("timed out")

    _client(
        tmp_path,
        investigation_copilot=OptionalProviderInvestigationCopilot(
            api_key="k", model="m", http_post=timeout_post
        ),
    )
    with TestClient(app) as client:
        client.post("/upload", data=FORM, follow_redirects=False)
        pid = client.post("/upload", data=FORM, follow_redirects=False).headers["location"].rsplit("/", 1)[-1]
        client.post(f"/observation/{pid}/confirm")
        client.post(f"/observation/{pid}/finalize", data={"one_health_sentence": "x"})
        r = client.post("/investigate/sites/coimbra/analyze", follow_redirects=False)
        assert r.status_code == 303
        page = client.get(r.headers["location"])
        assert page.status_code == 200
        assert "AI advisory unavailable (timeout)" in page.text
        api = client.get("/api" + r.headers["location"].removeprefix("/investigate")).json()
        assert api["ai_advisory"]["validation_status"] == "timeout"
        assert api["status"] == "SUCCEEDED"
