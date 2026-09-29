"""Per-browser observer pseudonym: derivation, cookie, display, privacy, migration."""

from __future__ import annotations

import hashlib
import logging
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.application.serialization import dumps_document, packet_to_document
from app.composition import build_services, reset_services, set_services
from app.demo.fixture_loader import load_fixture
from app.domain.enums import ActorType
from app.domain.errors import DomainValidationError
from app.domain.observer import (
    OBSERVER_COOKIE,
    UNKNOWN_OBSERVER_LABEL,
    observer_pseudonym,
    observer_ref_for_token,
)
from app.domain.packet import ObservationPacket
from app.domain.signal.value_objects import TimeWindow
from app.domain.sites import get_site
from app.domain.value_objects import Actor, FieldValue
from app.flags.engine import DeterministicFlagEngine
from app.main import app
from app.persistence.config import DatabaseSettings
from app.persistence.migrations_runner import apply_migrations, list_migration_files

PSEUDONYM_RE = re.compile(r"^Observer-[0-9A-F]{8}$")
SENTENCE = "Cited association — not a diagnosis."


@pytest.fixture
def services(tmp_path: Path):
    reset_services()
    svc = build_services(
        settings=DatabaseSettings(sqlite_path=tmp_path / "observer.sqlite3"),
        flag_engine=DeterministicFlagEngine(),
    )
    set_services(svc)
    yield svc
    reset_services()


def _submit_and_finalize(c: TestClient, *, foam: str, site: str = "coimbra") -> str:
    r = c.post(
        "/upload",
        data={"site": site, "foam": foam, "colour": "clear", "smell": "none"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    packet_id = r.headers["location"].rsplit("/", 1)[-1]
    assert c.post(f"/observation/{packet_id}/confirm", follow_redirects=False).status_code == 303
    fin = c.post(
        f"/observation/{packet_id}/finalize",
        data={"one_health_sentence": SENTENCE},
        follow_redirects=False,
    )
    assert fin.status_code == 303
    return packet_id


def _pseudonym_for(c: TestClient) -> tuple[str, str, str]:
    token = c.cookies.get(OBSERVER_COOKIE)
    assert token
    ref = observer_ref_for_token(token)
    return token, ref, observer_pseudonym(ref)


# --- derivation ---------------------------------------------------------------


def test_same_token_same_pseudonym_and_pinned_scheme() -> None:
    token = "00112233445566778899aabbccddeeff"
    ref = observer_ref_for_token(token)
    expected = hashlib.sha256(b"confirmgate/observer-ref/v1\x00" + token.encode()).hexdigest()
    assert ref == expected == observer_ref_for_token(token)
    assert observer_pseudonym(ref) == "Observer-" + expected[:8].upper()
    assert observer_pseudonym(ref) == "Observer-8ABE263B"
    assert PSEUDONYM_RE.match(observer_pseudonym(ref))
    assert token not in ref


def test_two_hundred_fixed_tokens_give_distinct_pseudonyms() -> None:
    tokens = [hashlib.md5(f"observer-{i}".encode()).hexdigest() for i in range(200)]
    assert len(set(tokens)) == 200
    labels = [observer_pseudonym(observer_ref_for_token(t)) for t in tokens]
    assert all(PSEUDONYM_RE.match(label) for label in labels)
    assert len(set(labels)) == 200


def test_invalid_inputs_never_produce_a_pseudonym() -> None:
    for bad in ("", "citizen", "g" * 32, "A" * 32, "0" * 31):
        with pytest.raises(DomainValidationError):
            observer_ref_for_token(bad)
    for bad in (None, "", "citizen", "0" * 63, "Z" * 64):
        assert observer_pseudonym(bad) == UNKNOWN_OBSERVER_LABEL
    with pytest.raises(DomainValidationError):
        ObservationPacket.create(get_site("coimbra"), observer_ref="not-a-ref")


# --- cookie -------------------------------------------------------------------


def test_cookie_attributes_and_set_only_once(services) -> None:
    with TestClient(app) as c:
        first = c.get("/upload")
        header = first.headers["set-cookie"]
        assert header.startswith(f"{OBSERVER_COOKIE}=")
        assert "HttpOnly" in header
        assert "SameSite=Lax" in header
        assert "Path=/" in header
        assert "Secure" not in header
        token = c.cookies.get(OBSERVER_COOKIE)
        assert re.fullmatch(r"[0-9a-f]{32}", token)
        assert "set-cookie" not in c.get("/upload").headers
        assert c.cookies.get(OBSERVER_COOKIE) == token


def test_cookie_secure_on_https(services) -> None:
    with TestClient(app, base_url="https://testserver") as c:
        assert "Secure" in c.get("/upload").headers["set-cookie"]


def test_invalid_cookie_is_replaced(services) -> None:
    with TestClient(app) as c:
        c.cookies.set(OBSERVER_COOKIE, "citizen")
        r = c.get("/upload")
        assert f"{OBSERVER_COOKIE}=" in r.headers["set-cookie"]


# --- display ------------------------------------------------------------------


def test_pseudonym_stable_across_page_loads_and_submissions(services) -> None:
    with TestClient(app) as c:
        c.get("/upload")
        token, ref, label = _pseudonym_for(c)
        assert PSEUDONYM_RE.match(label)
        first = _submit_and_finalize(c, foam="present")
        second = _submit_and_finalize(c, foam="absent")
        for pid in (first, second, first):
            html = c.get(f"/observation/{pid}").text
            assert label in html
            assert token not in html and ref not in html
        assert services.observation.get(first).packet.observer_ref == ref
        assert services.observation.get(second).packet.observer_ref == ref


def test_two_browsers_two_pseudonyms_in_one_analysis(services) -> None:
    with TestClient(app) as a, TestClient(app) as b:
        a.get("/upload")
        b.get("/upload")
        token_a, ref_a, label_a = _pseudonym_for(a)
        token_b, ref_b, label_b = _pseudonym_for(b)
        assert token_a != token_b and label_a != label_b
        assert PSEUDONYM_RE.match(label_a) and PSEUDONYM_RE.match(label_b)

        pid_a = _submit_and_finalize(a, foam="present")
        pid_b = _submit_and_finalize(b, foam="absent")

        r = a.post("/investigate/sites/coimbra/analyze", follow_redirects=False)
        assert r.status_code == 303
        run_url = r.headers["location"]
        run_id = run_url.rsplit("/", 1)[-1]
        html = a.get(run_url).text

        assert label_a in html and label_b in html
        assert html.count('class="pair-observer"') >= 2
        assert "disagrees about foam" in html
        for secret in (token_a, token_b, ref_a, ref_b):
            assert secret not in html

        api = a.get(f"/api/analyses/{run_id}").json()
        observers = {e["evidence_id"]: e["observer"] for e in api["evidence"]}
        assert observers == {pid_a: label_a, pid_b: label_b}
        api_text = a.get(f"/api/analyses/{run_id}").text
        for secret in (token_a, token_b, ref_a, ref_b):
            assert secret not in api_text

        review = a.get(f"/review/{pid_a}")
        assert review.status_code == 200
        assert label_a in review.text
        assert token_a not in review.text and ref_a not in review.text


def test_synthetic_fixture_rows_are_labelled_synthetic(services) -> None:
    outcome = services.analysis.analyze(
        site=get_site("coimbra"),
        time_window=TimeWindow(
            start=datetime(2026, 6, 1, tzinfo=timezone.utc),
            end=datetime(2026, 9, 30, tzinfo=timezone.utc),
        ),
        fixture_observations=list(load_fixture("C_contradiction")),
    )
    brief = services.brief.get_brief(outcome.run.run_id)
    assert {e.observer_label for e in brief.evidence} == {"Synthetic fixture"}


# --- privacy ------------------------------------------------------------------


def test_fhir_bundle_has_no_token_ref_or_pseudonym(services) -> None:
    with TestClient(app) as c:
        c.get("/upload")
        token, ref, label = _pseudonym_for(c)
        pid = _submit_and_finalize(c, foam="present")
        bundle = c.get("/fhir/bundle", params={"packet_id": pid})
        assert bundle.status_code == 200
        text = bundle.text
        for leaked in (token, ref, label, ref[:8].upper(), ref[:8], "Observer-"):
            assert leaked not in text
        page = c.get("/fhir", params={"packet_id": pid})
        assert page.status_code == 200
        assert token not in page.text and ref not in page.text


def test_token_never_logged_or_stored(services, caplog, tmp_path: Path) -> None:
    caplog.set_level(logging.DEBUG)
    with TestClient(app) as c:
        c.get("/upload")
        token, ref, _ = _pseudonym_for(c)
        pid = _submit_and_finalize(c, foam="present")
        c.post("/upload", data={"site": "coimbra"}, follow_redirects=False)
        c.post("/investigate/sites/coimbra/analyze", follow_redirects=False)
    assert token not in caplog.text and ref not in caplog.text

    conn = sqlite3.connect(tmp_path / "observer.sqlite3")
    dump = "\n".join(conn.iterdump())
    conn.close()
    assert token not in dump
    ref_lines = [line for line in dump.splitlines() if ref in line]
    assert ref_lines
    assert all(line.startswith('INSERT INTO "observation_packets"') for line in ref_lines)
    doc = services.observation.get(pid)
    assert ref not in dumps_document(packet_to_document(doc.packet))


def test_pseudonym_does_not_change_reproducibility_hashes(services, tmp_path: Path) -> None:
    with TestClient(app) as a, TestClient(app) as b:
        a.get("/upload")
        b.get("/upload")
        pids = [_submit_and_finalize(a, foam="present"), _submit_and_finalize(b, foam="absent")]
    site = get_site("coimbra")
    before = services.analysis.analyze_finalized_for_site(site=site)

    conn = sqlite3.connect(tmp_path / "observer.sqlite3")
    conn.execute(
        "UPDATE observation_packets SET observer_ref = ? WHERE packet_id = ?",
        ("f" * 64, pids[0]),
    )
    conn.execute("UPDATE observation_packets SET observer_ref = NULL WHERE packet_id = ?", (pids[1],))
    conn.commit()
    conn.close()

    after = services.analysis.analyze_finalized_for_site(site=site)
    assert after.snapshot.snapshot_hash == before.snapshot.snapshot_hash
    assert after.parameters_hash == before.parameters_hash
    assert sorted(r.message for r in after.relations) == sorted(
        r.message for r in before.relations
    )


# --- migration / old rows -----------------------------------------------------


def test_migration_preserves_pre_pseudonym_rows(tmp_path: Path) -> None:
    db = tmp_path / "pre005.sqlite3"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY NOT NULL,"
        " applied_at TEXT NOT NULL, name TEXT NOT NULL)"
    )
    for version, path in list_migration_files():
        if version >= 5:
            continue
        conn.executescript(path.read_text(encoding="utf-8"))
        conn.execute("INSERT INTO schema_migrations VALUES (?, 'legacy', ?)", (version, path.name))

    citizen = Actor(ActorType.CITIZEN, "citizen")
    system = Actor(ActorType.SYSTEM, "system-test")
    packet = ObservationPacket.create(
        get_site("coimbra"),
        author_actor_id="citizen",
        submitter_display="citizen",
        effective_at=datetime(2026, 9, 10, 9, 0, tzinfo=timezone.utc),
    )
    for code, value in (("foam", "present"), ("colour", "clear"), ("smell", "none")):
        packet.set_field(FieldValue(code=code, value=value), actor=citizen)
    packet.apply_flags([], actor=system)
    packet.mark_awaiting_confirm(actor=system)
    packet.confirm(actor=citizen)
    packet.finalize(actor=system)
    document_json = dumps_document(packet_to_document(packet))
    conn.execute(
        """
        INSERT INTO observation_packets (
            packet_id, site_ref_id, city, workflow_state, revision,
            document_json, flags_rules_version, created_at, updated_at
        ) VALUES (?, 'coimbra', 'Coimbra', 'FINALIZED', 1, ?, NULL,
                  '2026-09-10T09:05:00+00:00', '2026-09-10T09:05:00+00:00')
        """,
        (packet.packet_id, document_json),
    )
    conn.commit()

    assert apply_migrations(conn) == [5]
    row = conn.execute(
        "SELECT document_json, observer_ref FROM observation_packets WHERE packet_id = ?",
        (packet.packet_id,),
    ).fetchone()
    conn.close()
    assert row == (document_json, None)

    reset_services()
    svc = build_services(
        settings=DatabaseSettings(sqlite_path=db),
        flag_engine=DeterministicFlagEngine(),
    )
    set_services(svc)
    try:
        assert svc.observation.get(packet.packet_id).packet.observer_ref is None
        with TestClient(app) as c:
            html = c.get(f"/observation/{packet.packet_id}").text
            assert UNKNOWN_OBSERVER_LABEL in html
            r = c.post("/investigate/sites/coimbra/analyze", follow_redirects=False)
            run_id = r.headers["location"].rsplit("/", 1)[-1]
            api = c.get(f"/api/analyses/{run_id}").json()
            assert [e["observer"] for e in api["evidence"]] == [UNKNOWN_OBSERVER_LABEL]
    finally:
        reset_services()
