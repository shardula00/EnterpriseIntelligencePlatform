"""Integration tests for app/audit/service.py, against a live Postgres."""

import uuid

from app.audit.service import AuditAction, list_audit_logs, record_event
from app.auth.security import hash_password
from app.models.user import User


def _make_user(db_session) -> User:
    user = User(
        email=f"audit-svc-{uuid.uuid4().hex[:8]}@example.com",
        password_hash=hash_password("Password123"),
        full_name="Audit Test User",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_record_event_strips_forbidden_keys_from_metadata(db_session):
    user = _make_user(db_session)
    record_event(
        db_session,
        user_id=user.id,
        action=AuditAction.LOGIN_SUCCESS,
        metadata={"note": "fine", "password": "supersecret", "token": "abc.def.ghi"},
    )
    db_session.commit()

    entries, _ = list_audit_logs(db_session, user_id=user.id)
    assert entries[0].event_metadata == {"note": "fine"}


def test_record_event_with_no_metadata_stores_null(db_session):
    user = _make_user(db_session)
    record_event(db_session, user_id=user.id, action=AuditAction.LOGOUT)
    db_session.commit()

    entries, _ = list_audit_logs(db_session, user_id=user.id)
    assert entries[0].event_metadata is None


def test_list_audit_logs_resolves_the_users_email(db_session):
    user = _make_user(db_session)
    record_event(db_session, user_id=user.id, action=AuditAction.LOGIN_SUCCESS)
    db_session.commit()

    entries, _ = list_audit_logs(db_session, user_id=user.id)
    assert entries[0].user_email == user.email


def test_list_audit_logs_filters_by_action(db_session):
    user = _make_user(db_session)
    record_event(db_session, user_id=user.id, action=AuditAction.LOGIN_SUCCESS)
    record_event(db_session, user_id=user.id, action=AuditAction.LOGOUT)
    db_session.commit()

    entries, total = list_audit_logs(db_session, user_id=user.id, action=AuditAction.LOGOUT)
    assert total == 1
    assert entries[0].action == AuditAction.LOGOUT


def test_list_audit_logs_pagination(db_session):
    user = _make_user(db_session)
    for _ in range(5):
        record_event(db_session, user_id=user.id, action=AuditAction.LOGIN_SUCCESS)
    db_session.commit()

    page_1, total = list_audit_logs(db_session, user_id=user.id, limit=2, offset=0)
    page_2, _ = list_audit_logs(db_session, user_id=user.id, limit=2, offset=2)

    assert total == 5
    assert len(page_1) == 2
    assert len(page_2) == 2
    assert {e.id for e in page_1}.isdisjoint({e.id for e in page_2})


def test_list_audit_logs_orders_newest_first(db_session):
    user = _make_user(db_session)
    record_event(db_session, user_id=user.id, action=AuditAction.USER_REGISTERED)
    db_session.commit()
    record_event(db_session, user_id=user.id, action=AuditAction.LOGIN_SUCCESS)
    db_session.commit()

    entries, _ = list_audit_logs(db_session, user_id=user.id)
    assert entries[0].action == AuditAction.LOGIN_SUCCESS
    assert entries[1].action == AuditAction.USER_REGISTERED
