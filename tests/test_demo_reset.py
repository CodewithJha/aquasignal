"""Public-demo dataset protection: DEMO_MODE gate, reset, startup reset."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.composition import build_services, reset_services, set_services
from app.demo.config import DemoSettings
from app.demo.reset import DemoResetRefused, main, reset_demo_database
from app.domain.sites import get_site
from app.flags.engine import DeterministicFlagEngine
from app.main import app
from app.persistence.config import DatabaseSettings
from app.persistence.factory import connect, open_unit_of_work
from app.web.routes import configure_templates
from tests.db import POSTGRES, make_settings, sqlite_only

APP_DIR = Path(__file__).resolve().parents[1] / "app"
TEMPLATES_DIR = APP_DIR / "templates"
ON = DemoSettings(demo_mode=True)
OFF = DemoSettings(demo_mode=False)

# Fixture runs A+C, E, B (seed order) — must match scripts/seed_aquasignal_demo.py output.
SEED_SNAPSHOT_HASHES = [
    "41bacc93314eee1af12b1c40a1cba80536fb4d045995cfec2407d04d889e65f8",
    "3cad30895aa9b65ed8f9459837016b2dc262e88ccb53fe175e3820eb60c68ad6",
    "3dee53685ec6012f78879a42de31ab42472aa4a155b21ea2572ff122d75bab17",
]
SEED_PARAMETERS_HASH = "ca53e802f3e465bc320593aee4323d56d07d8bd70718bb2d3864eac8cb06a01d"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("DEMO_MODE", "DEMO_RESET_ON_START"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def settings(tmp_path: Path) -> DatabaseSettings:
    return make_settings(tmp_path / "demo.sqlite3")


def _rows(settings: DatabaseSettings, sql: str) -> list[tuple]:
    conn = connect(settings)
    try:
        return [tuple(r) for r in conn.execute(sql).fetchall()]
    finally:
        conn.close()


def _count(settings: DatabaseSettings, table: str) -> int:
    return _rows(settings, f"SELECT COUNT(*) FROM {table}")[0][0]


def _hashes(settings: DatabaseSettings) -> list[tuple]:
    return _rows(
        settings,
        "SELECT snapshot_hash, parameters_hash, detector_set_version, status "
        "FROM analysis_runs ORDER BY started_at, run_id",
    )


def _add_user_observation(settings: DatabaseSettings) -> str:
    services = build_services(settings=settings, flag_engine=DeterministicFlagEngine())
    return services.observation.create(get_site("coimbra"), author_actor_id="citizen-x").packet.packet_id


def _schema(settings: DatabaseSettings) -> tuple[list[tuple], list[tuple]]:
    migrations = _rows(settings, "SELECT version, name, applied_at FROM schema_migrations ORDER BY version")
    if POSTGRES:
        ddl = _rows(
            settings,
            "SELECT table_name, column_name, data_type, column_default FROM information_schema.columns "
            "WHERE table_schema = current_schema() ORDER BY table_name, column_name",
        ) + _rows(
            settings,
            "SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = current_schema() ORDER BY indexname",
        )
    else:
        ddl = _rows(settings, "SELECT type, name, sql FROM sqlite_master ORDER BY type, name")
    return migrations, ddl


# --- config -----------------------------------------------------------------


def test_demo_settings_default_off() -> None:
    s = DemoSettings.from_env()
    assert s.demo_mode is False
    assert s.reset_on_start is False
    assert s.should_reset_on_start is False


def test_demo_mode_enabled_recognized(monkeypatch: pytest.MonkeyPatch) -> None:
    for raw in ("true", "1", "YES", " on "):
        monkeypatch.setenv("DEMO_MODE", raw)
        assert DemoSettings.from_env().demo_mode is True
    monkeypatch.setenv("DEMO_MODE", "false")
    assert DemoSettings.from_env().demo_mode is False


def test_reset_on_start_requires_demo_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEMO_RESET_ON_START", "true")
    assert DemoSettings.from_env().should_reset_on_start is False
    monkeypatch.setenv("DEMO_MODE", "true")
    assert DemoSettings.from_env().should_reset_on_start is True


# --- reset gate -------------------------------------------------------------


def test_reset_refuses_without_demo_mode(settings: DatabaseSettings) -> None:
    packet_id = _add_user_observation(settings)
    with pytest.raises(DemoResetRefused):
        reset_demo_database(settings=settings, demo=OFF)
    assert _rows(settings, "SELECT packet_id FROM observation_packets") == [(packet_id,)]


def test_reset_refuses_by_default_env(settings: DatabaseSettings) -> None:
    packet_id = _add_user_observation(settings)
    with pytest.raises(DemoResetRefused):
        reset_demo_database(settings=settings)
    assert _count(settings, "observation_packets") == 1
    assert packet_id


@sqlite_only
def test_cli_refuses_and_rejects_arguments(
    settings: DatabaseSettings, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("DATABASE_URL", str(settings.sqlite_path))
    assert main([]) == 2
    assert "refused" in capsys.readouterr().err
    assert not settings.sqlite_path.exists()

    monkeypatch.setenv("DEMO_MODE", "true")
    assert main([str(settings.sqlite_path)]) == 2
    assert not settings.sqlite_path.exists()


# --- reset behaviour --------------------------------------------------------


def test_reset_restores_seed_state(settings: DatabaseSettings) -> None:
    first = reset_demo_database(settings=settings, demo=ON)
    assert (first.analysis_runs, first.evidence_items, first.investigation_cases) == (3, 29, 1)
    seeded_counts = {t: _count(settings, t) for t in ("evidence_items", "analysis_runs", "investigation_cases", "environmental_signals", "provenance_events")}

    packet_id = _add_user_observation(settings)
    assert _count(settings, "observation_packets") == 1

    second = reset_demo_database(settings=settings, demo=ON)
    assert second.observation_packets == 0
    assert _rows(settings, f"SELECT 1 FROM observation_packets WHERE packet_id = '{packet_id}'") == []
    assert {t: _count(settings, t) for t in seeded_counts} == seeded_counts
    assert _count(settings, "human_decisions") == 0


def test_reset_keeps_migrations_and_schema(settings: DatabaseSettings) -> None:
    conn, _factory = open_unit_of_work(settings)
    conn.close()
    before = _schema(settings)
    reset_demo_database(settings=settings, demo=ON)
    reset_demo_database(settings=settings, demo=ON)
    assert _schema(settings) == before
    assert [v for v, _n, _a in before[0]] == [1, 2, 3, 4, 5]


@sqlite_only
def test_reset_touches_only_database_files(settings: DatabaseSettings) -> None:
    def app_digest() -> str:
        h = hashlib.sha256()
        for p in sorted(APP_DIR.rglob("*")):
            if p.is_file() and "__pycache__" not in p.parts:
                h.update(p.relative_to(APP_DIR).as_posix().encode())
                h.update(p.read_bytes())
        return h.hexdigest()

    before = app_digest()
    reset_demo_database(settings=settings, demo=ON)
    assert app_digest() == before
    db = settings.sqlite_path.name
    produced = {p.name for p in settings.sqlite_path.parent.iterdir()}
    assert produced <= {db, f"{db}-wal", f"{db}-shm"}


def test_seeded_analysis_deterministic_across_resets(settings: DatabaseSettings) -> None:
    reset_demo_database(settings=settings, demo=ON)
    first = _hashes(settings)
    reset_demo_database(settings=settings, demo=ON)
    assert _hashes(settings) == first
    assert len(first) == 3
    assert all(row[2] == "aquasignal-detectors-a3-v2" and row[3] == "SUCCEEDED" for row in first)
    assert len({row[1] for row in first}) == 1
    assert [row[0] for row in first] == SEED_SNAPSHOT_HASHES
    assert first[0][1] == SEED_PARAMETERS_HASH


def test_seeded_rows_are_labelled_synthetic(settings: DatabaseSettings) -> None:
    reset_demo_database(settings=settings, demo=ON)
    rows = _rows(settings, "SELECT source_class, is_synthetic FROM evidence_items")
    assert rows and all(r == ("fixture", 1) for r in rows)


@sqlite_only
def test_cli_output_has_no_secrets_or_paths(
    settings: DatabaseSettings, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    secret = "sk-demo-secret-should-never-print"
    monkeypatch.setenv("AI_API_KEY", secret)
    monkeypatch.setenv("DATABASE_URL", str(settings.sqlite_path))
    monkeypatch.setenv("DEMO_MODE", "true")
    assert main([]) == 0
    out = capsys.readouterr()
    text = out.out + out.err
    assert "Demo dataset reset" in text
    for leak in (secret, str(settings.sqlite_path), settings.sqlite_path.name, "sqlite", "DELETE", "DATABASE_URL="):
        assert leak not in text


# --- startup ----------------------------------------------------------------


def _start_app(settings: DatabaseSettings) -> None:
    reset_services()
    set_services(build_services(settings=settings, flag_engine=DeterministicFlagEngine()))
    with TestClient(app) as client:
        assert client.get("/healthz").status_code == 200
    reset_services()


def test_startup_never_wipes_without_demo_mode(
    settings: DatabaseSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    _add_user_observation(settings)
    monkeypatch.setenv("DEMO_RESET_ON_START", "true")
    _start_app(settings)
    assert _count(settings, "observation_packets") == 1
    assert _count(settings, "analysis_runs") == 0


def test_startup_reset_when_both_flags_set(
    settings: DatabaseSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    _add_user_observation(settings)
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("DEMO_RESET_ON_START", "true")
    _start_app(settings)
    assert _count(settings, "observation_packets") == 0
    assert _count(settings, "analysis_runs") == 3


def test_demo_banner_only_in_demo_mode(settings: DatabaseSettings, monkeypatch: pytest.MonkeyPatch) -> None:
    reset_services()
    set_services(build_services(settings=settings, flag_engine=DeterministicFlagEngine()))
    try:
        configure_templates(TEMPLATES_DIR)
        with TestClient(app) as client:
            assert "data may be reset" not in client.get("/upload").text
            monkeypatch.setenv("DEMO_MODE", "true")
            configure_templates(TEMPLATES_DIR)
            assert "Public demo — data may be reset." in client.get("/upload").text
    finally:
        monkeypatch.delenv("DEMO_MODE", raising=False)
        configure_templates(TEMPLATES_DIR)
        reset_services()
