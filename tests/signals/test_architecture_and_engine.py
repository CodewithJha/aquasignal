"""Architecture + determinism + registry + engine tests for Phase A3."""

from __future__ import annotations

import ast
from pathlib import Path

from app.signals.engine import SignalEngine
from app.signals.models import DetectionStatus
from app.signals.registry import DETECTOR_SET_VERSION, default_registry
from tests.signals.conftest import make_contradiction_context, make_temporal_context
from tests.signals.fixture_loader import load_fixture

REPO = Path(__file__).resolve().parents[2]
SIGNALS = REPO / "app" / "signals"


def test_signals_do_not_import_persistence_web_ai_fhir_sqlite() -> None:
    forbidden = {
        "sqlite3",
        "app.persistence",
        "app.web",
        "app.ai",
        "app.fhir",
    }
    for py in SIGNALS.rglob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    names.add(alias.name.split(".")[0])
                    parts = alias.name.split(".")
                    if parts[0] == "app" and len(parts) > 1:
                        names.add(f"app.{parts[1]}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                parts = node.module.split(".")
                names.add(parts[0])
                if parts[0] == "app" and len(parts) > 1:
                    names.add(f"app.{parts[1]}")
        bad = names & forbidden
        assert not bad, f"{py.relative_to(REPO)} imports {bad}"


def test_registry_order_and_versions() -> None:
    reg = default_registry()
    assert reg.version == DETECTOR_SET_VERSION
    assert reg.descriptors() == (
        "temporal_baseline_shift:v1",
        "cross_observation_contradiction:v2",
    )


def test_engine_runs_both_detectors_deterministically(
    coimbra, analysis_window, baseline_window, recent_window
) -> None:
    evidence = load_fixture("A_temporal_shift")
    # Engine needs both param blocks; temporal params required for temporal detector.
    temporal_ctx = make_temporal_context(
        coimbra, analysis_window, baseline_window, recent_window, k=1.0
    )
    contra = make_contradiction_context(coimbra, analysis_window)
    merged = {
        **temporal_ctx.params,
        **contra.params,
    }
    from app.signals.models import AnalysisContext

    ctx = AnalysisContext(
        site=coimbra, time_window=analysis_window, params=merged
    )
    engine = SignalEngine()
    a = engine.analyze(evidence, ctx)
    b = engine.analyze(list(reversed(evidence)), ctx)
    assert [r.to_canonical_json() for r in a] == [r.to_canonical_json() for r in b]
    assert a[0].detector_id.value == "temporal_baseline_shift"
    assert a[-1].detector_id.value == "cross_observation_contradiction"
    assert any(r.status is DetectionStatus.SIGNAL for r in a)


def test_params_serialize_deterministically(
    baseline_window, recent_window
) -> None:
    from app.signals.params import TemporalBaselineParams

    p = TemporalBaselineParams(
        field_code="foam",
        baseline_window=baseline_window,
        recent_window=recent_window,
    )
    assert p.to_canonical_json() == p.to_canonical_json()
    assert "field_code" in p.to_canonical_json()


def test_ordinal_maps_isolated() -> None:
    from app.signals.ordinals import ORDINAL_FIELD_MAPS, to_ordinal

    assert to_ordinal("foam", "absent") == 0
    assert to_ordinal("foam", "present") == 1
    assert to_ordinal("foam", "abundant") == 2
    assert to_ordinal("macrophytes", "a") == 0
    assert to_ordinal("colour", "clear") is None
    assert "colour" not in ORDINAL_FIELD_MAPS
