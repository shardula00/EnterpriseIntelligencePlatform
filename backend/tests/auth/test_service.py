"""Integration tests for app/auth/service.py, against a live Postgres."""

import uuid

import pytest

from app.auth import service
from app.auth.errors import EmailAlreadyRegisteredError, InactiveUserError, InvalidCredentialsError


def _unique_email() -> str:
    return f"svc-test-{uuid.uuid4().hex[:8]}@example.com"


def test_register_user_hashes_the_password(db_session):
    email = _unique_email()
    user = service.register_user(db_session, email=email, password="Password123", full_name="A B")
    db_session.commit()

    assert user.password_hash != "Password123"
    assert "Password123" not in user.password_hash


def test_register_user_defaults_to_viewer_role(db_session):
    user = service.register_user(
        db_session, email=_unique_email(), password="Password123", full_name="A B"
    )
    db_session.commit()

    assert [r.name for r in user.roles] == ["VIEWER"]


def test_register_user_rejects_duplicate_email(db_session):
    email = _unique_email()
    service.register_user(db_session, email=email, password="Password123", full_name="First")
    db_session.commit()

    with pytest.raises(EmailAlreadyRegisteredError):
        service.register_user(db_session, email=email, password="Password456", full_name="Second")


def test_authenticate_user_succeeds_with_correct_password(db_session):
    email = _unique_email()
    service.register_user(db_session, email=email, password="Password123", full_name="A B")
    db_session.commit()

    user = service.authenticate_user(db_session, email=email, password="Password123")
    assert user.email == email


def test_authenticate_user_rejects_wrong_password(db_session):
    email = _unique_email()
    service.register_user(db_session, email=email, password="Password123", full_name="A B")
    db_session.commit()

    with pytest.raises(InvalidCredentialsError):
        service.authenticate_user(db_session, email=email, password="WrongPassword")


def test_authenticate_user_rejects_unknown_email(db_session):
    with pytest.raises(InvalidCredentialsError):
        service.authenticate_user(db_session, email=_unique_email(), password="whatever")


def test_wrong_password_and_unknown_email_give_identical_error_messages(db_session):
    # No account-enumeration signal: both failure modes must be indistinguishable.
    email = _unique_email()
    service.register_user(db_session, email=email, password="Password123", full_name="A B")
    db_session.commit()

    try:
        service.authenticate_user(db_session, email=email, password="WrongPassword")
        wrong_password_message = None
    except InvalidCredentialsError as exc:
        wrong_password_message = str(exc)

    try:
        service.authenticate_user(db_session, email=_unique_email(), password="WrongPassword")
        unknown_email_message = None
    except InvalidCredentialsError as exc:
        unknown_email_message = str(exc)

    assert wrong_password_message == unknown_email_message
    assert wrong_password_message is not None


def test_authenticate_user_rejects_inactive_user(db_session):
    email = _unique_email()
    user = service.register_user(
        db_session, email=email, password="Password123", full_name="A B"
    )
    user.is_active = False
    db_session.commit()

    with pytest.raises(InactiveUserError):
        service.authenticate_user(db_session, email=email, password="Password123")


def test_logout_increments_token_version(db_session):
    user = service.register_user(
        db_session, email=_unique_email(), password="Password123", full_name="A B"
    )
    db_session.commit()
    original_version = user.token_version

    service.logout(db_session, user)
    db_session.commit()

    assert user.token_version == original_version + 1


def test_get_user_by_id_returns_none_for_unknown_id(db_session):
    assert service.get_user_by_id(db_session, uuid.uuid4()) is None
