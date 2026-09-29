"""Phase 6 architecture — templates/routes stay thin; FlagEngine not in routes."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "app" / "web"
TEMPLATES = ROOT / "app" / "templates"


def test_routes_do_not_instantiate_flag_engine() -> None:
    src = (WEB / "routes.py").read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = ""
            if isinstance(func, ast.Name):
                name = func.id
            elif isinstance(func, ast.Attribute):
                name = func.attr
            assert name not in {
                "DeterministicFlagEngine",
                "NullFlagEngine",
            }, "routes must not construct FlagEngine"


def test_routes_do_not_import_sqlite_or_mapper() -> None:
    src = (WEB / "routes.py").read_text()
    tree = ast.parse(src)
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    assert "sqlite3" not in imports
    assert "app.fhir.mapper" not in imports
    assert not any(i.startswith("app.persistence") for i in imports)


def test_templates_have_no_sql() -> None:
    for path in TEMPLATES.glob("*.html"):
        text = path.read_text().lower()
        assert "select *" not in text
        assert "insert into" not in text
        assert "sqlite3" not in text


def test_composition_defaults_to_deterministic() -> None:
    src = (ROOT / "app" / "composition.py").read_text()
    assert "DeterministicFlagEngine" in src
    # NullFlagEngine must not be the production default in composition.
    assert "flag_engine = NullFlagEngine" not in src
    assert 'NullFlagEngine()' not in src
