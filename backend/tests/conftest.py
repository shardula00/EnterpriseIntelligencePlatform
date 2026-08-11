"""Shared pytest fixtures.

Tests run against the real Postgres started via infra/docker-compose.yml
(same as Phase 1's health check) - Phase 2 tests write real data (datasets,
their physical tables), so an autouse fixture cleans up anything a test
creates, keeping the shared dev database tidy and tests independent of run
order.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.ingestion import service
from app.main import app
from app.models.dataset import Dataset

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def _cleanup_datasets_created_during_test():
    session: Session = SessionLocal()
    existing_ids = set(session.execute(select(Dataset.id)).scalars())
    session.close()

    yield

    session = SessionLocal()
    try:
        current_ids = set(session.execute(select(Dataset.id)).scalars())
        for dataset_id in current_ids - existing_ids:
            try:
                service.delete_dataset(session, dataset_id)
            except Exception:
                session.rollback()
    finally:
        session.close()
