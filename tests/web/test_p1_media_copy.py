"""P1.5 — photo copy is honest: content is never analyzed."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.composition import build_services, reset_services, set_services
from app.flags.engine import DeterministicFlagEngine
from app.main import app
from app.persistence.config import DatabaseSettings

NOTE = "Image content is not analyzed by this system."


def test_upload_and_review_pages_state_media_is_not_analyzed(tmp_path: Path) -> None:
    reset_services()
    set_services(
        build_services(
            settings=DatabaseSettings(sqlite_path=tmp_path / "media.sqlite3"),
            flag_engine=DeterministicFlagEngine(),
        )
    )
    try:
        with TestClient(app) as client:
            upload = client.get("/upload").text
            assert NOTE in upload
            assert "Bytes are noted" not in upload

            r = client.post(
                "/upload",
                data={"site": "oslo", "foam": "present", "colour": "clear", "smell": "none"},
                files={"photo": ("bank.jpg", b"\xff\xd8fake", "image/jpeg")},
                follow_redirects=False,
            )
            pid = r.headers["location"].rsplit("/", 1)[-1]
            client.post(f"/observation/{pid}/request-review")
            review = client.get(f"/review/{pid}").text
            assert NOTE in review
            assert "bank.jpg" in review
    finally:
        reset_services()
