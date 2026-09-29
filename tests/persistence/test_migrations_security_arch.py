"""Schema migration, security, and architecture boundary tests."""

from __future__ import annotations

import ast
import sqlite3
from pathlib import Path


from app.application.service import ObservationService
from app.domain.packet import ObservationPacket
from app.domain.value_objects import Actor
from app.persistence.config import resolve_sqlite_path
from app.persistence.migrations_runner import apply_migrations, list_migration_files


REPO_ROOT = Path(__file__).resolve().parents[2]
DOMAIN_ROOT = REPO_ROOT / "app" / "domain"
FLAGS_ROOT = REPO_ROOT / "app" / "flags"
APP_ROOT = REPO_ROOT / "app"


def test_migrations_ordered_and_applied(tmp_path: Path) -> None:
    files = list_migration_files()
    assert files, "expected at least one migration SQL file"
    versions = [v for v, _ in files]
    assert versions == sorted(versions)
    assert versions[0] == 1

    db = tmp_path / "mig.sqlite3"
    conn = sqlite3.connect(str(db))
    newly = apply_migrations(conn)
    assert 1 in newly
    rows = conn.execute("SELECT version, name FROM schema_migrations").fetchall()
    assert rows
    # Idempotent
    again = apply_migrations(conn)
    assert again == []
    conn.close()


def test_database_url_resolution(tmp_path: Path) -> None:
    root = tmp_path
    default = resolve_sqlite_path("", project_root=root)
    assert default == (root / "data" / "confirmgate.sqlite3").resolve()

    rel = resolve_sqlite_path("sqlite:///relative.db", project_root=root)
    assert rel == (root / "relative.db").resolve()


def test_parameterized_sql_only_in_persistence() -> None:
    """Heuristic: no f-string SQL with user-looking concatenation in repos."""
    persistence = APP_ROOT / "persistence"
    offenders: list[str] = []
    for py in persistence.rglob("*.py"):
        text = py.read_text()
        # Ban classic string-format SQL anti-patterns with packet_id interpolation
        if 'f"SELECT' in text or "f'SELECT" in text or 'f"INSERT' in text:
            offenders.append(str(py))
        if 'f"UPDATE' in text or 'f"DELETE' in text:
            offenders.append(str(py))
    assert not offenders, offenders


def test_no_secrets_in_provenance(
    service: ObservationService,
    fresh_packet: ObservationPacket,
    citizen: Actor,
) -> None:
    # Even if a caller stuffed a secret into notes, provenance payloads from
    # domain intents should not invent API keys; assert no key-like fields.
    fresh_packet.set_notes("ordinary note", actor=citizen)
    service.persist_new(fresh_packet)
    for event in service.list_provenance(fresh_packet.packet_id):
        blob = str(event.to_audit_dict()).lower()
        assert "api_key" not in blob
        assert "password" not in blob
        assert "secret" not in blob


def _imports_in(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
                if alias.name.startswith("app."):
                    parts = alias.name.split(".")
                    if len(parts) > 1:
                        names.add(f"app.{parts[1]}")
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
            parts = node.module.split(".")
            if parts[0] == "app" and len(parts) > 1:
                names.add(f"app.{parts[1]}")
    return names


FORBIDDEN_DOMAIN = {
    "fastapi",
    "starlette",
    "jinja2",
    "sqlalchemy",
    "sqlite3",
    "httpx",
    "requests",
    "openai",
    "app.fhir",
    "app.ai",
    "app.web",
    "app.flags",
    "app.provenance",
    "app.persistence",
    "app.application",
}


def test_domain_has_no_persistence_or_web_imports() -> None:
    for py in DOMAIN_ROOT.glob("*.py"):
        imports = _imports_in(py)
        bad = imports & FORBIDDEN_DOMAIN
        assert not bad, f"{py.name} imports forbidden: {bad}"


FORBIDDEN_FLAGS = FORBIDDEN_DOMAIN | {"app.persistence", "app.application"}


def test_flags_have_no_persistence_web_fhir_ai_imports() -> None:
    for py in FLAGS_ROOT.rglob("*.py"):
        imports = _imports_in(py)
        bad = imports & {
            "fastapi",
            "sqlite3",
            "sqlalchemy",
            "app.fhir",
            "app.ai",
            "app.web",
            "app.provenance",
            "app.persistence",
            "app.application",
        }
        assert not bad, f"{py}: {bad}"
        for node in ast.walk(ast.parse(py.read_text())):
            if isinstance(node, ast.ImportFrom) and node.module:
                parts = node.module.split(".")
                if parts[0] == "app" and len(parts) > 1:
                    assert parts[1] in {"domain", "flags"}, (
                        f"{py} imports app.{parts[1]}"
                    )


def test_isolated_temp_db_not_shared_machine_path(
    db_path: Path, service: ObservationService, coimbra, citizen: Actor
) -> None:
    assert "tmp" in str(db_path).lower() or db_path.parent != Path.home()
    packet = ObservationPacket.create(coimbra, author_actor_id=citizen.actor_id)
    service.persist_new(packet)
    assert db_path.exists()
