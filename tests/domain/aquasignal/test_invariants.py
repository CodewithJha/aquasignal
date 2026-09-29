"""Cross-cutting AquaSignal A1 invariants — no diagnostic score types."""

from __future__ import annotations

import ast
from pathlib import Path

FORBIDDEN_TYPE_NAMES = frozenset(
    {
        "TrustScore",
        "RiskIndex",
        "PollutionLevel",
        "PathogenAlert",
        "PollutionScore",
        "DiseaseRisk",
    }
)


def test_no_forbidden_diagnostic_types_in_domain_packages() -> None:
    root = Path(__file__).resolve().parents[3] / "app" / "domain"
    packages = ("evidence", "signal", "investigation")
    found: list[str] = []
    for pkg in packages:
        for py in (root / pkg).rglob("*.py"):
            tree = ast.parse(py.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name in FORBIDDEN_TYPE_NAMES:
                    found.append(f"{py}:{node.name}")
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id in FORBIDDEN_TYPE_NAMES:
                            found.append(f"{py}:{target.id}")
    assert not found, f"Forbidden diagnostic types present: {found}"


def test_time_window_half_open() -> None:
    from datetime import datetime, timezone

    from app.domain.errors import DomainValidationError
    from app.domain.signal.value_objects import TimeWindow
    import pytest

    start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    end = datetime(2026, 9, 22, tzinfo=timezone.utc)
    w = TimeWindow(start=start, end=end)
    assert w.contains(start) is True
    assert w.contains(end) is False
    with pytest.raises(DomainValidationError):
        TimeWindow(start=end, end=start)
