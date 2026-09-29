"""A4 architecture: orchestration has no detector math; signals stay pure."""

from __future__ import annotations

import ast
from pathlib import Path

APP = Path(__file__).resolve().parents[3] / "app"
APPLICATION = APP / "application"
SIGNALS = APP / "signals"
PERSISTENCE = APP / "persistence"


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
                parts = alias.name.split(".")
                if parts[0] == "app" and len(parts) > 1:
                    names.add(f"app.{parts[1]}")
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
            parts = node.module.split(".")
            if parts[0] == "app" and len(parts) > 1:
                names.add(f"app.{parts[1]}")
    return names


def test_signals_still_do_not_import_persistence() -> None:
    forbidden = {
        "sqlite3",
        "app.persistence",
        "app.web",
        "app.ai",
        "app.fhir",
        "app.application",
    }
    for py in SIGNALS.rglob("*.py"):
        names = _imported_modules(py)
        bad = names & forbidden
        assert not bad, f"{py.name} imports {bad}"


def test_orchestration_does_not_put_math_in_repos() -> None:
    """Persistence must not import detector modules; math stays in app.signals."""
    forbidden_detectors = {
        "app.signals.detectors",
        "app.signals.stats",
        "app.signals.ordinals",
    }
    for py in PERSISTENCE.rglob("*.py"):
        names = _imported_modules(py)
        bad = {n for n in names if any(n.startswith(f) for f in forbidden_detectors)}
        assert not bad, f"{py.relative_to(APP)} imports detector math: {bad}"


def test_analysis_service_coordinates_engine_not_math() -> None:
    """AnalysisService may import SignalEngine; must not import stats/ordinals."""
    path = APPLICATION / "analysis_service.py"
    names = _imported_modules(path)
    assert "app.signals.engine" in names or any(
        n.startswith("app.signals.engine") for n in names
    )
    assert "app.signals.stats" not in names
    assert "app.signals.ordinals" not in names
    assert "sqlite3" not in names
    assert "app.persistence" not in names
    assert "app.web" not in names


def test_application_aquasignal_modules_avoid_sql() -> None:
    for name in (
        "analysis_service.py",
        "investigation_service.py",
        "investigation_brief.py",
        "evidence_gate.py",
        "evidence_mapping.py",
        "result_mapping.py",
        "params_hash.py",
    ):
        path = APPLICATION / name
        assert path.exists(), name
        names = _imported_modules(path)
        assert "sqlite3" not in names, name
        assert "app.persistence" not in names, name


def test_web_investigation_does_not_import_signal_engine() -> None:
    web = APP / "web" / "investigation_routes.py"
    names = _imported_modules(web)
    assert "app.signals.engine" not in names
    assert "app.signals.detectors" not in names
    assert "sqlite3" not in names
    assert "app.persistence" not in names
