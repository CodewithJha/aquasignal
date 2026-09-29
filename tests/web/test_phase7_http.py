"""Phase 7 web: reviewer queue/detail and POST accept/reject/edit (TestClient)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.composition import build_services, reset_services, set_services
from app.domain.enums import WorkflowState
from app.flags.engine import DeterministicFlagEngine
from app.main import app
from tests.db import make_settings


@pytest.fixture
def client(tmp_path: Path):
    reset_services()
    services = build_services(
        settings=make_settings(tmp_path / "p7http.sqlite3"),
        flag_engine=DeterministicFlagEngine(),
    )
    set_services(services)
    with TestClient(app) as c:
        yield c, services
    reset_services()


def _submit(client: TestClient) -> str:
    r = client.post(
        "/upload",
        data={
            "site": "coimbra",
            "foam": "present",
            "colour": "clear",
            "smell": "none",
            "notes": "p7",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    return r.headers["location"].rsplit("/", 1)[-1]


def _escalate(client: TestClient, packet_id: str) -> None:
    r = client.post(
        f"/observation/{packet_id}/request-review",
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == f"/review/{packet_id}"


def test_queue_and_detail(client) -> None:
    c, _ = client
    packet_id = _submit(c)
    _escalate(c, packet_id)

    queue = c.get("/review")
    assert queue.status_code == 200
    assert "Reviewer worklist" in queue.text
    assert "NEEDS_REVIEW" in queue.text
    assert packet_id[:10] in queue.text
    assert "trust" not in queue.text.lower() or "no trust" in queue.text.lower()

    detail = c.get(f"/review/{packet_id}")
    assert detail.status_code == 200
    assert "Findings" in detail.text
    assert "Provenance" in detail.text
    assert "export FHIR" in detail.text
    assert "Auth not implemented" in detail.text
    # Accept copy must stress confirm ≠ finalize/export
    assert "CONFIRMED" in detail.text or "confirm authority" in detail.text.lower()


def test_post_accept_confirmed_no_fhir(client) -> None:
    c, services = client
    packet_id = _submit(c)
    _escalate(c, packet_id)
    rev = services.reviewer.get(packet_id).revision

    acc = c.post(
        f"/review/{packet_id}/accept",
        data={"revision": str(rev)},
        follow_redirects=False,
    )
    assert acc.status_code == 303
    assert services.reviewer.get(packet_id).packet.workflow_state == (
        WorkflowState.CONFIRMED
    )

    fhir = c.get(f"/fhir/bundle?packet_id={packet_id}")
    assert fhir.status_code == 409


def test_post_reject_requires_reason(client) -> None:
    c, services = client
    packet_id = _submit(c)
    _escalate(c, packet_id)
    rev = services.reviewer.get(packet_id).revision

    bad = c.post(
        f"/review/{packet_id}/reject",
        data={"revision": str(rev), "reason_code": ""},
        follow_redirects=False,
    )
    assert bad.status_code in {400, 409}
    assert services.reviewer.get(packet_id).packet.workflow_state == (
        WorkflowState.NEEDS_REVIEW
    )

    ok = c.post(
        f"/review/{packet_id}/reject",
        data={
            "revision": str(services.reviewer.get(packet_id).revision),
            "reason_code": "prohibited_claim",
        },
        follow_redirects=False,
    )
    assert ok.status_code == 303
    assert services.reviewer.get(packet_id).packet.workflow_state == (
        WorkflowState.REJECTED
    )


def test_post_edit_revalidate(client) -> None:
    c, services = client
    packet_id = _submit(c)
    _escalate(c, packet_id)
    rev = services.reviewer.get(packet_id).revision
    r = c.post(
        f"/review/{packet_id}/edit",
        data={
            "revision": str(rev),
            "foam": "absent",
            "colour": "green",
            "smell": "mild",
            "notes": "edited",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    pkt = services.reviewer.get(packet_id).packet
    assert pkt.workflow_state == WorkflowState.NEEDS_REVIEW
    assert pkt.fields["foam"].value == "absent"


def test_accept_wrong_state(client) -> None:
    c, _ = client
    packet_id = _submit(c)
    # Still FLAGGED
    r = c.post(f"/review/{packet_id}/accept", data={"revision": "1"})
    assert r.status_code in {400, 409}
    assert "NEEDS_REVIEW" in r.text or "Accept" in r.text


def test_concurrency_conflict_http(client) -> None:
    c, services = client
    packet_id = _submit(c)
    _escalate(c, packet_id)
    stale = services.reviewer.get(packet_id).revision
    services.reviewer.edit(
        packet_id,
        fields={
            k: services.reviewer.get(packet_id).packet.fields[k]
            for k in ("foam", "colour", "smell")
            if k in services.reviewer.get(packet_id).packet.fields
        },
        expected_revision=stale,
    )
    r = c.post(
        f"/review/{packet_id}/accept",
        data={"revision": str(stale)},
    )
    assert r.status_code == 409
    assert "changed" in r.text.lower() or "revision" in r.text.lower()


def test_no_get_mutation(client) -> None:
    c, services = client
    packet_id = _submit(c)
    _escalate(c, packet_id)
    before = services.reviewer.get(packet_id).packet.workflow_state
    for path in (
        f"/review/{packet_id}/accept",
        f"/review/{packet_id}/reject",
        f"/review/{packet_id}/edit",
    ):
        r = c.get(path)
        assert r.status_code in {405, 404}
    assert services.reviewer.get(packet_id).packet.workflow_state == before
