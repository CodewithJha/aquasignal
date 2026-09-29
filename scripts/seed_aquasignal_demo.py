"""Seed Coimbra AquaSignal demo analyses (A3 fixtures + A4 AnalysisService).

Usage (from repo root, venv active):

    python scripts/seed_aquasignal_demo.py

Then open http://127.0.0.1:8000/investigate/sites/coimbra

Appends the synthetic runs defined in ``app.demo.seed`` (temporal shift +
contradiction with an open case, insufficient evidence, stable control).
To wipe the database back to exactly this seeded state instead, use
``DEMO_MODE=true python -m app.demo.reset``.

Real (non-synthetic) analyses need no script: finalize observations in
ConfirmGate, then press "Analyze finalized observations" on the site page.

Never overwrites prior runs. Labels fixtures as synthetic.
Loads via app.demo.fixture_loader (never tests.*).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.composition import build_services, reset_services, set_services
from app.demo import seed


def seed_coimbra_demo(*, open_case: bool = True) -> list[str]:
    """Run fixture analyses for Coimbra; return new run_ids (newest last)."""
    reset_services()
    services = build_services()
    set_services(services)
    run_ids = seed.seed_coimbra_demo(
        services.analysis, services.investigation, open_case=open_case
    )

    print("Seeded Coimbra AquaSignal demo runs:")
    for rid in run_ids:
        print(f"  - {rid}")
    print("Open: http://127.0.0.1:8000/investigate/sites/coimbra")
    print(f"Primary brief: http://127.0.0.1:8000/investigate/analyses/{run_ids[0]}")
    return run_ids


def main() -> None:
    seed_coimbra_demo()


if __name__ == "__main__":
    main()
