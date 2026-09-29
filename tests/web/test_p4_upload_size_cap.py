"""P4.4 — oversized uploads are refused with a friendly 413 (MAX_UPLOAD_BYTES)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi import FastAPI, Form
from fastapi.testclient import TestClient

from app.composition import build_services, reset_services, set_services
from app.flags.engine import DeterministicFlagEngine
from app.main import app
from app.persistence.config import DatabaseSettings
from app.web.request_limits import (
    DEFAULT_MAX_UPLOAD_BYTES,
    MaxBodySizeMiddleware,
    max_upload_bytes,
)

FORM = {"site": "coimbra", "foam": "present", "colour": "clear", "smell": "none"}


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "cap.sqlite3"


@pytest.fixture
def client(db_path: Path):
    reset_services()
    set_services(
        build_services(
            settings=DatabaseSettings(sqlite_path=db_path),
            flag_engine=DeterministicFlagEngine(),
        )
    )
    with TestClient(app) as c:
        yield c
    reset_services()


def _packet_count(db_path: Path) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute("SELECT COUNT(*) FROM observation_packets").fetchone()[0]
    finally:
        conn.close()


def test_default_cap_rejects_large_photo(client, db_path, monkeypatch) -> None:
    monkeypatch.delenv("MAX_UPLOAD_BYTES", raising=False)
    photo = b"\xff" * (DEFAULT_MAX_UPLOAD_BYTES + 1)
    r = client.post(
        "/upload",
        data=FORM,
        files={"photo": ("river.jpg", photo, "image/jpeg")},
        follow_redirects=False,
    )
    assert r.status_code == 413
    assert "Upload too large" in r.text
    assert "10 MB" in r.text
    assert "Traceback" not in r.text
    assert _packet_count(db_path) == 0


def test_env_cap_is_honoured_and_small_upload_still_works(client, db_path, monkeypatch) -> None:
    monkeypatch.setenv("MAX_UPLOAD_BYTES", "4096")
    big = client.post(
        "/upload",
        data=FORM,
        files={"photo": ("river.jpg", b"x" * 8000, "image/jpeg")},
        follow_redirects=False,
    )
    assert big.status_code == 413
    assert _packet_count(db_path) == 0

    ok = client.post(
        "/upload",
        data=FORM,
        files={"photo": ("river.jpg", b"x" * 100, "image/jpeg")},
        follow_redirects=False,
    )
    assert ok.status_code == 303
    assert _packet_count(db_path) == 1


def test_chunked_body_without_content_length_is_capped() -> None:
    mini = FastAPI()
    mini.add_middleware(MaxBodySizeMiddleware, max_bytes=100)

    @mini.post("/echo")
    def echo(note: str = Form("")) -> dict[str, int]:
        return {"n": len(note)}

    def chunks():
        for _ in range(10):
            yield b"note=" + b"a" * 50

    with TestClient(mini) as c:
        r = c.post(
            "/echo",
            content=chunks(),
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
        assert r.status_code == 413
        assert "Upload too large" in r.text
        assert c.post("/echo", data={"note": "short"}).json() == {"n": 5}


@pytest.mark.parametrize(
    "raw, expected",
    [(None, DEFAULT_MAX_UPLOAD_BYTES), ("abc", DEFAULT_MAX_UPLOAD_BYTES), ("0", DEFAULT_MAX_UPLOAD_BYTES), ("2048", 2048)],
)
def test_max_upload_bytes_parsing(monkeypatch, raw, expected) -> None:
    if raw is None:
        monkeypatch.delenv("MAX_UPLOAD_BYTES", raising=False)
    else:
        monkeypatch.setenv("MAX_UPLOAD_BYTES", raw)
    assert max_upload_bytes() == expected
