"""Phase 6 unit tests — forms, flag presentation, errors, DeterministicFlagEngine wiring."""

from __future__ import annotations

from pathlib import Path


from app.application.citizen_flow import CitizenFlowService
from app.application.service import ObservationService
from app.composition import build_services
from app.domain.enums import Severity
from app.domain.packet import make_flag
from app.domain.sites import SEED_SITES, get_site, list_sites
from app.flags.engine import DeterministicFlagEngine, NullFlagEngine
from app.persistence.config import DatabaseSettings
from app.web.errors import map_exception
from app.web.flags_view import present_flags
from app.web.forms import parse_submission


def test_sites_catalog_matches_five_oah_cities() -> None:
    sites = list_sites()
    assert len(sites) == 5
    assert set(SEED_SITES) == {s.site_id for s in sites}
    assert get_site("coimbra").city == "Coimbra"


def test_parse_submission_happy_path() -> None:
    parsed = parse_submission(
        {
            "site": "coimbra",
            "foam": "present",
            "colour": "clear",
            "smell": "none",
        }
    )
    assert parsed.ok
    assert parsed.site_id == "coimbra"
    assert set(parsed.fields) == {"foam", "colour", "smell"}


def test_parse_rejects_unsupported_and_excluded_values() -> None:
    bad = parse_submission({"site": "coimbra", "foam": "purple-sparkle"})
    assert not bad.ok
    assert any("Unsupported value" in e.message for e in bad.errors)

    excluded = parse_submission({"site": "coimbra", "bmwp": "12", "foam": "present"})
    assert not excluded.ok
    assert any("bmwp" in e.field or "excluded" in e.message for e in excluded.errors)


def test_parse_rejects_unknown_site_via_empty() -> None:
    parsed = parse_submission({"foam": "present"})
    assert not parsed.ok
    assert any(e.field == "site" for e in parsed.errors)


def test_flag_presentation_groups_and_blocks_confirm() -> None:
    flags = [
        make_flag(
            rule_id="completeness.required_field.foam",
            severity=Severity.SOFT_BLOCK_FINALIZE,
            code="COMPLETENESS_REQUIRED",
            message="foam required",
        ),
        make_flag(
            rule_id="media.blur",
            severity=Severity.WARN,
            code="MEDIA_WARN",
            message="maybe blurry",
        ),
        make_flag(
            rule_id="vocabulary.invalid_value.foam",
            severity=Severity.HARD_REJECT,
            code="VOCAB_INVALID_VALUE",
            message="bad foam",
        ),
    ]
    groups = present_flags(flags)
    assert len(groups.needs_correction) == 2
    assert len(groups.warnings) == 1
    assert groups.can_confirm is False
    assert "%" not in groups.needs_correction[0].guidance


def test_error_mapping_citizen_messages() -> None:
    from app.application.citizen_flow import CitizenFlowError
    from app.application.errors import PacketNotFound

    err = map_exception(CitizenFlowError("confirm_blocked", "hard flags remain"))
    assert err.http_status == 409
    assert "hard flags" in err.message

    missing = map_exception(PacketNotFound("abc"))
    assert missing.http_status == 404


def test_observation_service_wires_deterministic_engine(tmp_path: Path) -> None:
    settings = DatabaseSettings(sqlite_path=tmp_path / "wire.sqlite3")
    services = build_services(settings=settings)
    assert isinstance(services.flag_engine, DeterministicFlagEngine)
    assert isinstance(services.observation.flag_engine, DeterministicFlagEngine)
    assert services.observation.flag_engine is services.flag_engine
    assert isinstance(services.flow, CitizenFlowService)
    assert services.ai.model_id == "null"


def test_observation_service_null_fallback_for_tests(tmp_path: Path) -> None:
    from app.persistence.factory import open_unit_of_work

    settings = DatabaseSettings(sqlite_path=tmp_path / "null.sqlite3")
    _conn, factory = open_unit_of_work(settings)
    svc = ObservationService(factory)  # default NullFlagEngine
    assert isinstance(svc.flag_engine, NullFlagEngine)

    svc2 = ObservationService(factory, flag_engine=DeterministicFlagEngine())
    assert isinstance(svc2.flag_engine, DeterministicFlagEngine)
