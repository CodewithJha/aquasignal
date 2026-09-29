"""Test re-export — canonical loader lives in ``app.demo.fixture_loader``."""

from __future__ import annotations

from app.demo.fixture_loader import FIXTURE_DIR, list_fixture_names, load_fixture

__all__ = ["FIXTURE_DIR", "list_fixture_names", "load_fixture"]
