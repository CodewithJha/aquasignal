"""Architecture boundary tests for app.flags."""

from __future__ import annotations

import ast
from pathlib import Path

FLAGS_ROOT = Path(__file__).resolve().parents[2] / "app" / "flags"

FORBIDDEN = {
    "fastapi",
    "starlette",
    "jinja2",
    "sqlalchemy",
    "sqlite3",
    "httpx",
    "requests",
    "openai",
    "ollama",
    "http",
    "urllib",
    "aiohttp",
    "boto3",
    "app.fhir",
    "app.ai",
    "app.web",
    "app.provenance",
    "app.persistence",
    "app.application",
}


def _imports_in(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
            parts = node.module.split(".")
            if parts[0] == "app" and len(parts) > 1:
                names.add(f"app.{parts[1]}")
    return names


def test_flags_package_does_not_import_forbidden_layers() -> None:
    offenders: list[str] = []
    for py in FLAGS_ROOT.rglob("*.py"):
        imports = _imports_in(py)
        bad = imports & FORBIDDEN
        if bad:
            offenders.append(f"{py.relative_to(FLAGS_ROOT.parent)}: {sorted(bad)}")
    assert not offenders, "Forbidden imports in flags:\n" + "\n".join(offenders)


def test_flags_may_import_domain_only_from_app() -> None:
    for py in FLAGS_ROOT.rglob("*.py"):
        for node in ast.walk(ast.parse(py.read_text())):
            if isinstance(node, ast.ImportFrom) and node.module:
                parts = node.module.split(".")
                if parts[0] == "app" and len(parts) > 1:
                    assert parts[1] in {"domain", "flags"}, (
                        f"{py} imports app.{parts[1]}"
                    )
