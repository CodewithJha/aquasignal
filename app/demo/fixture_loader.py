"""Load labelled AquaSignal fixtures (synthetic — never live OAH).

Canonical JSON lives under ``app/demo/aquasignal/``. Seed scripts and tests
share this loader; nothing under ``app/`` imports the ``tests`` package.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from app.domain.evidence.enums import EvidenceSourceClass
from app.domain.sites import get_site
from app.signals.models import EvidenceObservation

FIXTURE_DIR = Path(__file__).resolve().parent / "aquasignal"


def list_fixture_names() -> list[str]:
    if not FIXTURE_DIR.is_dir():
        return []
    return sorted(p.stem for p in FIXTURE_DIR.glob("*.json"))


def load_fixture(name: str) -> list[EvidenceObservation]:
    """Load ``app/demo/aquasignal/{name}.json`` into EvidenceObservations."""
    path = FIXTURE_DIR / f"{name}.json"
    if not path.is_file():
        raise FileNotFoundError(f"AquaSignal fixture not found: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw.get("source_class") != "fixture":
        raise ValueError(f"fixture {name!r} must set source_class=fixture")
    if raw.get("is_synthetic") is not True:
        raise ValueError(f"fixture {name!r} must set is_synthetic=true")
    site = get_site(raw["site_id"])
    out: list[EvidenceObservation] = []
    for row in raw["observations"]:
        out.append(
            EvidenceObservation(
                evidence_id=row["evidence_id"],
                site=site,
                observed_at=datetime.fromisoformat(row["observed_at"]),
                source_class=EvidenceSourceClass.FIXTURE,
                is_synthetic=True,
                fields=dict(row["fields"]),
                payload_ref=f"fixture:{name}:{row['evidence_id']}",
                content_hash=f"fixture-hash-{row['evidence_id']}",
                license_tag="fixture-owned-mit",
            )
        )
    return out
