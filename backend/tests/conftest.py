"""Shared pytest fixtures.

Tests run against the real Postgres started via infra/docker-compose.yml
(same as Phase 1's health check). Phase 2/3 tests write real data
(datasets, their physical tables); Phase 4 tests write real users, roles,
and audit log rows - autouse fixtures clean up anything a test creates,
keeping the shared dev database tidy and tests independent of run order.

Phase 4 auth design note: `client` is admin-authenticated by default. That
keeps every pre-Phase-4 test (ingestion, KPIs) working completely
unchanged - those tests are about ingestion/KPI *behavior*, not permission
enforcement, which gets its own dedicated coverage in tests/auth/ and
tests/rbac/ via the role-specific fixtures below.
"""

import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.security import create_access_token, hash_password
from app.config import get_settings
from app.db import SessionLocal
from app.ingestion import service
from app.main import app
from app.models.analytics import AnalyticsQuery
from app.models.audit import AuditLog
from app.models.dataset import Dataset
from app.models.document import Document, RagQuery
from app.models.ml_run import MLRun
from app.models.user import Role, User
from app.rbac.seed import seed_roles_and_permissions

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session", autouse=True)
def _seed_rbac_catalog() -> None:
    """Idempotent - ensures ADMIN/ANALYST/VIEWER and the permission catalog
    exist before any test runs, the same seeding scripts/bootstrap_admin.py
    does for a real deployment."""
    db = SessionLocal()
    try:
        seed_roles_and_permissions(db)
    finally:
        db.close()


def _create_user_with_role(db: Session, role_name: str) -> User:
    role = db.execute(select(Role).where(Role.name == role_name)).scalar_one()
    user = User(
        email=f"test-{role_name.lower()}-{uuid.uuid4().hex[:8]}@example.com",
        password_hash=hash_password("Password123"),
        full_name=f"Test {role_name.title()}",
        roles=[role],
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _bearer_header(user: User) -> dict[str, str]:
    token = create_access_token(user.id, user.token_version, get_settings())
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def admin_user(db_session: Session) -> User:
    return _create_user_with_role(db_session, "ADMIN")


@pytest.fixture
def analyst_user(db_session: Session) -> User:
    return _create_user_with_role(db_session, "ANALYST")


@pytest.fixture
def viewer_user(db_session: Session) -> User:
    return _create_user_with_role(db_session, "VIEWER")


@pytest.fixture
def admin_headers(admin_user: User) -> dict[str, str]:
    return _bearer_header(admin_user)


@pytest.fixture
def analyst_headers(analyst_user: User) -> dict[str, str]:
    return _bearer_header(analyst_user)


@pytest.fixture
def viewer_headers(viewer_user: User) -> dict[str, str]:
    return _bearer_header(viewer_user)


@pytest.fixture
def client(admin_headers: dict[str, str]) -> TestClient:
    test_client = TestClient(app)
    test_client.headers.update(admin_headers)
    return test_client


@pytest.fixture
def unauthenticated_client() -> TestClient:
    return TestClient(app)


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


@pytest.fixture(autouse=True)
def _cleanup_users_created_during_test():
    session: Session = SessionLocal()
    existing_ids = set(session.execute(select(User.id)).scalars())
    session.close()

    yield

    session = SessionLocal()
    try:
        current_ids = set(session.execute(select(User.id)).scalars())
        for user_id in current_ids - existing_ids:
            user = session.get(User, user_id)
            if user is not None:
                session.delete(user)
        session.commit()
    finally:
        session.close()


@pytest.fixture(autouse=True)
def _cleanup_audit_logs_created_during_test():
    session: Session = SessionLocal()
    existing_ids = set(session.execute(select(AuditLog.id)).scalars())
    session.close()

    yield

    session = SessionLocal()
    try:
        current_ids = set(session.execute(select(AuditLog.id)).scalars())
        new_ids = current_ids - existing_ids
        if new_ids:
            session.execute(AuditLog.__table__.delete().where(AuditLog.id.in_(new_ids)))
            session.commit()
    finally:
        session.close()


@pytest.fixture(autouse=True)
def _cleanup_ml_runs_created_during_test():
    """Declared last so its teardown runs first (pytest tears fixtures down
    in reverse setup order) - it must delete each run's joblib artifact
    file *before* `_cleanup_datasets_created_during_test`'s teardown
    cascade-deletes the MLRun row out from under it (ml_runs.dataset_id is
    ON DELETE CASCADE, see app/models/ml_run.py)."""
    session: Session = SessionLocal()
    existing_ids = set(session.execute(select(MLRun.id)).scalars())
    session.close()

    yield

    session = SessionLocal()
    try:
        new_runs = [r for r in session.execute(select(MLRun)).scalars() if r.id not in existing_ids]
        for run in new_runs:
            if run.artifact_path:
                Path(run.artifact_path).unlink(missing_ok=True)
            session.delete(run)
        session.commit()
    finally:
        session.close()


@pytest.fixture(autouse=True)
def _cleanup_documents_created_during_test():
    """Same ID-diffing pattern as datasets/ML runs - also removes each
    document's retained raw file (best-effort, mirrors the MLRun artifact
    cleanup) so a full test run doesn't accumulate files on disk."""
    session: Session = SessionLocal()
    existing_ids = set(session.execute(select(Document.id)).scalars())
    session.close()

    yield

    session = SessionLocal()
    try:
        settings = get_settings()
        new_docs = [
            d for d in session.execute(select(Document)).scalars() if d.id not in existing_ids
        ]
        for document in new_docs:
            if document.source_file_path:
                (settings.rag_document_storage_dir / document.source_file_path).unlink(
                    missing_ok=True
                )
            session.delete(document)
        session.commit()
    finally:
        session.close()


@pytest.fixture(autouse=True)
def _cleanup_rag_queries_created_during_test():
    session: Session = SessionLocal()
    existing_ids = set(session.execute(select(RagQuery.id)).scalars())
    session.close()

    yield

    session = SessionLocal()
    try:
        current_ids = set(session.execute(select(RagQuery.id)).scalars())
        new_ids = current_ids - existing_ids
        if new_ids:
            session.execute(RagQuery.__table__.delete().where(RagQuery.id.in_(new_ids)))
            session.commit()
    finally:
        session.close()


@pytest.fixture(autouse=True)
def _cleanup_analytics_queries_created_during_test():
    """Same ID-diffing pattern as RAG queries above. dataset_id CASCADEs
    (see app/models/analytics.py), so this is only load-bearing for tests
    that query against a dataset *not* also created (and thus cleaned up)
    within the same test."""
    session: Session = SessionLocal()
    existing_ids = set(session.execute(select(AnalyticsQuery.id)).scalars())
    session.close()

    yield

    session = SessionLocal()
    try:
        current_ids = set(session.execute(select(AnalyticsQuery.id)).scalars())
        new_ids = current_ids - existing_ids
        if new_ids:
            session.execute(AnalyticsQuery.__table__.delete().where(AnalyticsQuery.id.in_(new_ids)))
            session.commit()
    finally:
        session.close()
