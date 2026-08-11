"""Shared pytest fixtures.

Phase 1 has no domain data to fix up before/after tests - the only test is
the health check, which is read-only. This file exists now so later
phases (which will need DB-resetting fixtures) have an obvious place to
add them.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
