"""A6 hardening — FAILED persistence, fixture loader location, fields on evidence."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock


from app.application.analysis_service import AnalysisService
from app.demo.fixture_loader import FIXTURE_DIR, load_fixture
from app.domain.investigation.enums import AnalysisRunStatus
from app.domain.signal.value_objects import TimeWindow
from app.domain.sites import get_site
from app.signals.engine import SignalEngine
from tests.application.aquasignal.conftest import make_analysis_params


def test_fixture_loader_lives_under_app_demo() -> None:
    assert "app/demo" in str(FIXTURE_DIR).replace("\\", "/")
    assert (FIXTURE_DIR / "A_temporal_shift.json").is_file()
    rows = load_fixture("A_temporal_shift")
    assert len(rows) >= 8
    assert all(r.is_synthetic for r in rows)
    assert rows[0].fields.get("foam")


def test_seed_script_does_not_import_tests_package() -> None:
    seed = Path(__file__).resolve().parents[3] / "scripts" / "seed_aquasignal_demo.py"
    text = seed.read_text(encoding="utf-8")
    assert "from tests." not in text
    assert "import tests" not in text
    assert "app.demo.fixture_loader" in text


def test_failed_run_persisted_no_orphan_started(uow_factory, analysis) -> None:
    coimbra = get_site("coimbra")
    window = TimeWindow(
        start=datetime(2026, 6, 1, tzinfo=timezone.utc),
        end=datetime(2026, 9, 30, tzinfo=timezone.utc),
    )
    baseline = TimeWindow(
        start=datetime(2026, 6, 1, tzinfo=timezone.utc),
        end=datetime(2026, 8, 1, tzinfo=timezone.utc),
    )
    recent = TimeWindow(
        start=datetime(2026, 9, 1, tzinfo=timezone.utc),
        end=datetime(2026, 9, 30, tzinfo=timezone.utc),
    )
    params = make_analysis_params(coimbra, window, baseline, recent)
    fixtures = load_fixture("B_stable_control")

    boom = MagicMock(spec=SignalEngine)
    boom.detector_set_version = "detectors@0.1.0"
    boom.analyze.side_effect = RuntimeError("detector exploded")

    failing = AnalysisService(uow_factory, signal_engine=boom)
    outcome = failing.analyze(
        site=coimbra,
        time_window=window,
        fixture_observations=fixtures,
        params=params,
    )
    assert outcome.run.status is AnalysisRunStatus.FAILED
    assert outcome.signals == ()
    loaded = analysis.get_run(outcome.run.run_id)
    assert loaded.status is AnalysisRunStatus.FAILED
    assert loaded.site_id == "coimbra"
    assert loaded.error
    assert "STARTED" not in loaded.status.value


def test_succeeded_run_self_describing_scope(analysis, coimbra) -> None:
    window = TimeWindow(
        start=datetime(2026, 6, 1, tzinfo=timezone.utc),
        end=datetime(2026, 9, 30, tzinfo=timezone.utc),
    )
    baseline = TimeWindow(
        start=datetime(2026, 6, 1, tzinfo=timezone.utc),
        end=datetime(2026, 8, 1, tzinfo=timezone.utc),
    )
    recent = TimeWindow(
        start=datetime(2026, 9, 1, tzinfo=timezone.utc),
        end=datetime(2026, 9, 30, tzinfo=timezone.utc),
    )
    params = make_analysis_params(coimbra, window, baseline, recent)
    outcome = analysis.analyze(
        site=coimbra,
        time_window=window,
        fixture_observations=load_fixture("B_stable_control"),
        params=params,
    )
    assert outcome.run.status is AnalysisRunStatus.SUCCEEDED
    assert outcome.run.site_id == "coimbra"
    assert outcome.run.time_window.start == window.start
    assert outcome.run.time_window.end == window.end
    # Normalized fields persisted on EvidenceItem — brief does not need fixture catalog.
    from app.application.investigation_brief import InvestigationBriefService

    brief = InvestigationBriefService(analysis._uow_factory).get_brief(outcome.run.run_id)
    assert brief.evidence
    assert any(ev.fields for ev in brief.evidence)
