from __future__ import annotations

import pytest

from tests.db import POSTGRES, drop_created_schemas


@pytest.fixture(scope="session", autouse=True)
def _drop_postgres_test_schemas():
    yield
    if POSTGRES:
        drop_created_schemas()
