"""P0/P1 — same-visit contradiction semantics + investigation brief presentation.

Real submissions are timestamped at submit time, so the same-day pair comes
from the web flow and the 30-days-later observation is built at service level
with an explicit ``effective_at`` (no observation-date UI exists).
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.composition import build_services, reset_services, set_services
from app.demo.fixture_loader import load_fixture
from app.domain.enums import ActorType
from app.domain.evidence.enums import EvidenceSourceClass
from app.domain.packet import ObservationPacket
from app.domain.signal.value_objects import TimeWindow
from app.domain.sites import get_site
from app.domain.value_objects import Actor, FieldValue
from app.flags.engine import DeterministicFlagEngine
from app.main import app
from app.persistence.config import DatabaseSettings
from app.signals.models import EvidenceObservation
from app.signals.params import ContradictionParams, TemporalBaselineParams


@pytest.fixture
def client(tmp_path: Path):
    reset_services()
    services = build_services(
        settings=DatabaseSettings(sqlite_path=tmp_path / "p0p1.sqlite3"),
        flag_engine=DeterministicFlagEngine(),
    )
    set_services(services)
    with TestClient(app) as c:
        yield c, services
    reset_services()


def _submit_and_finalize(c: TestClient, *, site: str, foam: str) -> str:
    r = c.post(
        "/upload",
        data={"site": site, "foam": foam, "colour": "clear", "smell": "none"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    packet_id = r.headers["location"].rsplit("/", 1)[-1]
    assert c.post(f"/observation/{packet_id}/confirm", follow_redirects=False).status_code == 303
    fin = c.post(
        f"/observation/{packet_id}/finalize",
        data={"one_health_sentence": "Cited association — not a diagnosis."},
        follow_redirects=False,
    )
    assert fin.status_code == 303
    return packet_id


def _finalized_packet_at(services, *, site: str, when: datetime, foam: str) -> str:
    citizen = Actor(ActorType.CITIZEN, "citizen-later-visit")
    system = Actor(ActorType.SYSTEM, "system-test")
    packet = ObservationPacket.create(
        get_site(site),
        author_actor_id=citizen.actor_id,
        submitter_display="Later visit",
        effective_at=when,
    )
    for code, value in (("foam", foam), ("colour", "clear"), ("smell", "none")):
        packet.set_field(FieldValue(code=code, value=value), actor=citizen)
    packet.apply_flags([], actor=system)
    packet.mark_awaiting_confirm(actor=system)
    packet.confirm(actor=citizen)
    packet.finalize(actor=system)
    services.observation.persist_new(packet)
    return packet.packet_id


def _fixture(eid: str, when: datetime, fields: dict[str, str]) -> EvidenceObservation:
    return EvidenceObservation(
        evidence_id=eid,
        site=get_site("coimbra"),
        observed_at=when,
        source_class=EvidenceSourceClass.FIXTURE,
        is_synthetic=True,
        fields=fields,
    )


def _analysis_window() -> TimeWindow:
    return TimeWindow(
        start=datetime(2026, 6, 1, tzinfo=timezone.utc),
        end=datetime(2026, 9, 30, tzinfo=timezone.utc),
    )


def _seed_params() -> dict:
    return {
        "temporal_baseline_shift": TemporalBaselineParams(
            field_code="foam",
            baseline_window=TimeWindow(
                start=datetime(2026, 6, 1, tzinfo=timezone.utc),
                end=datetime(2026, 8, 1, tzinfo=timezone.utc),
            ),
            recent_window=TimeWindow(
                start=datetime(2026, 9, 1, tzinfo=timezone.utc),
                end=datetime(2026, 9, 30, tzinfo=timezone.utc),
            ),
            threshold_multiplier=1.0,
        ),
        "cross_observation_contradiction": ContradictionParams(),
    }


# --- Part 3: product story ------------------------------------------------------


def test_ghent_same_day_disagreement_but_not_thirty_days_later(client) -> None:
    c, services = client
    a = _submit_and_finalize(c, site="ghent", foam="present")
    b = _submit_and_finalize(c, site="ghent", foam="absent")
    later = _finalized_packet_at(
        services,
        site="ghent",
        when=datetime.now(timezone.utc) + timedelta(days=30),
        foam="present",
    )

    r = c.post("/investigate/sites/ghent/analyze", follow_redirects=False)
    assert r.status_code == 303
    run_id = r.headers["location"].rsplit("/", 1)[-1]

    api = c.get(f"/api/analyses/{run_id}").json()
    assert {e["evidence_id"] for e in api["evidence"]} == {a, b, later}
    assert api["pair_counts"]["observations_analysed"] == 3
    assert api["pair_counts"]["pairs_compared"] == 1
    assert api["pair_counts"]["disagreeing_pairs"] == 1
    assert api["pair_counts"]["agreeing_pairs"] == 0
    assert api["pair_counts"]["comparison_window"] == "24 h"
    (pair,) = api["observation_pairs"]
    assert {pair["left_evidence_id"], pair["right_evidence_id"]} == {a, b}
    assert pair["outcome"] == "disagree"
    assert [f["field_code"] for f in pair["conflicting_fields"]] == ["foam"]
    for rel in api["contradictions"]:
        assert later not in (rel["left"]["evidence_id"], rel["right"]["evidence_id"])
    contradiction = [s for s in api["signals"] if s["signal_type"] == "contradiction"]
    assert contradiction and contradiction[0]["detector_version"] == "v2"
    assert contradiction[0]["metrics"]["pairs_outside_comparison_window"] == 2

    page = c.get(f"/investigate/analyses/{run_id}").text
    assert "1 observation pair disagrees about foam" in page
    assert "3 finalized observations" in page
    assert f"/observation/{later}" in page  # still visible as evidence


def test_same_day_identical_web_submissions_are_duplicates(client) -> None:
    c, _ = client
    _submit_and_finalize(c, site="oslo", foam="present")
    _submit_and_finalize(c, site="oslo", foam="present")
    run_id = c.post("/investigate/sites/oslo/analyze", follow_redirects=False).headers[
        "location"
    ].rsplit("/", 1)[-1]
    api = c.get(f"/api/analyses/{run_id}").json()
    assert api["pair_counts"]["duplicate_pairs"] == 1
    assert api["pair_counts"]["agreeing_pairs"] == 0
    assert api["counts"]["supporting"] == 0
    assert api["counts"]["duplicates"] == 3  # foam, colour, smell
    assert "look like duplicate" in " ".join(api["findings"]) or "looks like duplicate" in " ".join(
        api["findings"]
    )


# --- Seeded flagship outcome + reproducibility ---------------------------------


def test_flagship_fixture_outcome_and_reproducibility(client) -> None:
    _, services = client
    coimbra = get_site("coimbra")
    evidence = list(load_fixture("A_temporal_shift")) + list(load_fixture("C_contradiction"))
    runs = [
        services.analysis.analyze(
            site=coimbra,
            time_window=_analysis_window(),
            fixture_observations=evidence,
            params=_seed_params(),
        )
        for _ in range(2)
    ]
    first, second = runs
    assert first.parameters_hash == second.parameters_hash
    assert first.snapshot.snapshot_hash == second.snapshot.snapshot_hash

    def rel_keys(outcome):
        return sorted(
            (r.relation_type.value, r.left_ref, r.right_ref, r.rationale_code, r.message)
            for r in outcome.relations
        )

    assert rel_keys(first) == rel_keys(second)

    brief = services.brief.get_brief(first.run.run_id)
    assert brief.pair_summary.pairs_compared == 3
    assert brief.pair_summary.disagreeing_pairs == 2
    assert brief.pair_summary.agreeing_pairs == 1
    assert brief.pair_summary.duplicate_pairs == 0
    assert brief.detector_set_version == "aquasignal-detectors-a3-v2"
    assert {(d.detector_id, d.detector_version) for d in brief.detector_versions} == {
        ("cross_observation_contradiction", "v2"),
        ("temporal_baseline_shift", "v1"),
    }


def test_pair_conflicting_fields_only_list_detector_compared_fields(client) -> None:
    _, services = client
    t0 = datetime(2026, 9, 10, 8, 0, tzinfo=timezone.utc)
    evidence = [
        _fixture(
            "fx_a",
            t0,
            {"foam": "present", "macrophytes_non_native": "yes", "colour": "mud"},
        ),
        _fixture(
            "fx_b",
            t0 + timedelta(hours=1),
            {"foam": "absent", "macrophytes_non_native": "no", "colour": "clear"},
        ),
    ]
    outcome = services.analysis.analyze(
        site=get_site("coimbra"),
        time_window=_analysis_window(),
        fixture_observations=evidence,
        params=_seed_params(),
    )
    brief = services.brief.get_brief(outcome.run.run_id)
    (pair,) = brief.disagreeing_pairs
    assert [c.field_code for c in pair.conflicting_fields] == ["foam"]
    assert not any("macrophytes_non_native" in f for f in brief.findings)
    assert not any("colour" in f for f in brief.findings)


# --- Parts 4–7: brief presentation ------------------------------------------------


def _many_conflicts_run(services) -> str:
    t0 = datetime(2026, 9, 10, 8, 0, tzinfo=timezone.utc)
    evidence = [
        _fixture("fx_1", t0, {"foam": "present", "colour": "clear"}),
        _fixture("fx_2", t0 + timedelta(hours=1), {"foam": "absent", "colour": "brown"}),
        _fixture("fx_3", t0 + timedelta(hours=2), {"foam": "present", "colour": "clear"}),
        _fixture("fx_4", t0 + timedelta(hours=3), {"foam": "absent", "colour": "clear"}),
        _fixture("fx_5", t0 + timedelta(hours=4), {"foam": "abundant", "colour": "clear"}),
    ]
    outcome = services.analysis.analyze(
        site=get_site("coimbra"),
        time_window=_analysis_window(),
        fixture_observations=evidence,
        params=_seed_params(),
    )
    return outcome.run.run_id


def test_brief_summary_labels_top_three_and_show_all(client) -> None:
    c, services = client
    run_id = _many_conflicts_run(services)
    api = c.get(f"/api/analyses/{run_id}").json()
    disagree = [p for p in api["observation_pairs"] if p["outcome"] == "disagree"]
    assert len(disagree) > 3
    # Most differing fields first: fx_2 differs on foam AND colour from fx_1/fx_3.
    assert len(disagree[0]["conflicting_fields"]) == 2

    page = c.get(f"/investigate/analyses/{run_id}").text
    for label in (
        "Investigation summary",
        "Observation pairs compared",
        "Pairs that disagree",
        "Pairs that agree",
        "Duplicate pairs",
        "Detector signals",
        "Human decisions",
        "What we found",
        "Why?",
        "Human decision",
        "Technical details",
    ):
        assert label in page, label
    assert "SYNTHETIC FIXTURE" in page
    assert "5 synthetic fixture observations" in page

    head, _, rest = page.partition('<details class="show-all">')
    assert head.count('class="pair-card"') == 3
    assert f"Show all {len(disagree)} conflicts" in page
    assert page.count('class="pair-card"') == len(disagree)

    # Technical identifiers live inside the collapsed technical details.
    tech = page.split('<details class="tech-details">', 1)[1].split("</details>", 1)[0]
    brief_repro = api["reproducibility"]
    for value in (
        brief_repro["snapshot_hash"],
        brief_repro["parameters_hash"],
        "aquasignal-detectors-a3-v2",
        "cross_observation_contradiction:v2",
        "DeterministicFlagEngine",
        "vocab-canon@1",
    ):
        assert value in tech, value
    before_tech = page.split('<details class="tech-details">', 1)[0]
    assert brief_repro["snapshot_hash"] not in before_tech
    assert "DeterministicFlagEngine" not in before_tech
    assert "aquasignal-detectors" not in before_tech

    # AI disabled copy; no bare 'AI: null' anywhere.
    assert "AI advisory: disabled. Deterministic analysis is complete without it." in page
    assert "AI: null" not in page
    assert "packet" not in before_tech.lower().replace("confirmgate_packet", "")

    # No evidence lost: every observation id is in the page and in the API.
    for eid in ("fx_1", "fx_2", "fx_3", "fx_4", "fx_5"):
        assert eid in page
    assert len(api["evidence"]) == 5
    # Backward-compatible keys retained.
    for key in ("counts", "contradictions", "supports_messages", "signals", "reproducibility"):
        assert key in api


def test_brief_case_and_decision_still_work(client) -> None:
    c, services = client
    run_id = _many_conflicts_run(services)
    url = f"/investigate/analyses/{run_id}"
    assert "Open investigation case" in c.get(url).text
    assert c.post(f"{url}/cases", follow_redirects=False).status_code == 303
    assert c.post(f"{url}/cases", follow_redirects=False).status_code == 303
    assert len(services.brief.get_brief(run_id).cases) == 1
    page = c.get(url).text
    case_id = re.search(r"/investigate/cases/(case_[0-9a-f]+)/decisions", page).group(1)
    version = re.search(r'name="expected_version" value="(\d+)"', page).group(1)
    ok = c.post(
        f"/investigate/cases/{case_id}/decisions",
        data={"decision_code": "note", "rationale": "Ask for a repeat visit.", "expected_version": version},
        follow_redirects=False,
    )
    assert ok.status_code == 303
    stale = c.post(
        f"/investigate/cases/{case_id}/decisions",
        data={"decision_code": "note", "rationale": "Stale.", "expected_version": version},
    )
    assert stale.status_code == 409
    after = c.get(url).text
    assert "Ask for a repeat visit." in after
    assert "1 human decision" in after


def test_temporal_insufficiency_finding_is_explicit(client) -> None:
    c, services = client
    outcome = services.analysis.analyze(
        site=get_site("coimbra"),
        time_window=_analysis_window(),
        fixture_observations=load_fixture("E_insufficient"),
        params=_seed_params(),
    )
    api = c.get(f"/api/analyses/{outcome.run.run_id}").json()
    findings = api["findings"]
    assert (
        "Temporal baseline (foam): insufficient evidence (2 of 5 baseline and 1 of 3 "
        "recent observations)." in findings
    )
    assert any("no two observations were recorded close enough" in f for f in findings)
    assert api["pair_counts"]["pairs_compared"] == 0
