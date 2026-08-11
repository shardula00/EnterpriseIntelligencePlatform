"""Integration tests for /auth/* against a live Postgres, via the real
HTTP layer (register -> login -> me -> logout), plus the token_version
revocation mechanism and the audit trail those actions produce.
"""

import uuid

from app.models.audit import AuditLog
from app.models.user import User


def _unique_email() -> str:
    return f"api-test-{uuid.uuid4().hex[:8]}@example.com"


def _register(client, email: str, password: str = "Password123", full_name: str = "Test User"):
    return client.post(
        "/auth/register", json={"email": email, "password": password, "full_name": full_name}
    )


def _login(client, email: str, password: str = "Password123"):
    return client.post("/auth/login", json={"email": email, "password": password})


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def test_register_succeeds_and_never_returns_a_password_hash(unauthenticated_client):
    email = _unique_email()
    response = _register(unauthenticated_client, email)

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == email
    assert body["roles"] == ["VIEWER"]
    assert "password" not in body
    assert "password_hash" not in body
    assert "hashed_password" not in body


def test_register_duplicate_email_returns_409(unauthenticated_client):
    email = _unique_email()
    _register(unauthenticated_client, email)

    response = _register(unauthenticated_client, email)
    assert response.status_code == 409


def test_register_rejects_short_password(unauthenticated_client):
    response = _register(unauthenticated_client, _unique_email(), password="short")
    assert response.status_code == 422


def test_register_rejects_invalid_email(unauthenticated_client):
    response = unauthenticated_client.post(
        "/auth/register",
        json={"email": "not-an-email", "password": "Password123", "full_name": "A B"},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


def test_login_succeeds_with_correct_credentials(unauthenticated_client):
    email = _unique_email()
    _register(unauthenticated_client, email)

    response = _login(unauthenticated_client, email)
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert len(body["access_token"]) > 20


def test_login_rejects_wrong_password(unauthenticated_client):
    email = _unique_email()
    _register(unauthenticated_client, email)

    response = _login(unauthenticated_client, email, password="WrongPassword")
    assert response.status_code == 401


def test_login_rejects_unknown_email(unauthenticated_client):
    response = _login(unauthenticated_client, _unique_email())
    assert response.status_code == 401


def test_login_rejects_inactive_user(unauthenticated_client, client, db_session):
    # `client` (admin-authenticated) creates+deactivates a user via the real
    # admin API, then we confirm that user really cannot log in.
    email = _unique_email()
    create_response = client.post(
        "/users", json={"email": email, "password": "Password123", "full_name": "Deactivated"}
    )
    user_id = create_response.json()["id"]
    client.patch(f"/users/{user_id}", json={"is_active": False})

    response = _login(unauthenticated_client, email)
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# /auth/me
# ---------------------------------------------------------------------------


def test_me_returns_the_authenticated_user(unauthenticated_client):
    email = _unique_email()
    _register(unauthenticated_client, email)
    token = _login(unauthenticated_client, email).json()["access_token"]

    response = unauthenticated_client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["email"] == email


def test_me_without_a_token_returns_401(unauthenticated_client):
    assert unauthenticated_client.get("/auth/me").status_code == 401


def test_me_with_an_invalid_token_returns_401(unauthenticated_client):
    response = unauthenticated_client.get(
        "/auth/me", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Logout / token_version revocation
# ---------------------------------------------------------------------------


def test_logout_invalidates_the_token(unauthenticated_client):
    email = _unique_email()
    _register(unauthenticated_client, email)
    token = _login(unauthenticated_client, email).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    assert unauthenticated_client.get("/auth/me", headers=headers).status_code == 200

    logout_response = unauthenticated_client.post("/auth/logout", headers=headers)
    assert logout_response.status_code == 204

    # The same token must now be rejected everywhere, not just for /auth/me.
    assert unauthenticated_client.get("/auth/me", headers=headers).status_code == 401
    assert unauthenticated_client.get("/datasets", headers=headers).status_code == 401


def test_logout_does_not_invalidate_a_freshly_issued_second_token(unauthenticated_client):
    email = _unique_email()
    _register(unauthenticated_client, email)
    first_token = _login(unauthenticated_client, email).json()["access_token"]

    unauthenticated_client.post(
        "/auth/logout", headers={"Authorization": f"Bearer {first_token}"}
    )

    # Logging in again after logout must issue a token that works.
    second_token = _login(unauthenticated_client, email).json()["access_token"]
    response = unauthenticated_client.get(
        "/auth/me", headers={"Authorization": f"Bearer {second_token}"}
    )
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Audit trail produced by these endpoints
# ---------------------------------------------------------------------------


def test_registration_and_login_produce_audit_events(unauthenticated_client, db_session):
    email = _unique_email()
    _register(unauthenticated_client, email)
    _login(unauthenticated_client, email)

    user = db_session.query(User).filter(User.email == email).one()
    actions = {
        row.action
        for row in db_session.query(AuditLog).filter(AuditLog.user_id == user.id).all()
    }
    assert "user.registered" in actions
    assert "auth.login.success" in actions


def test_failed_login_produces_an_audit_event_without_the_password(
    unauthenticated_client, db_session
):
    email = _unique_email()
    _register(unauthenticated_client, email)
    _login(unauthenticated_client, email, password="WrongPassword")

    failed_events = db_session.query(AuditLog).filter(AuditLog.action == "auth.login.failed").all()
    matching = [
        e
        for e in failed_events
        if e.event_metadata and e.event_metadata.get("attempted_email") == email
    ]
    assert len(matching) == 1
    assert matching[0].user_id is None  # unknown-at-login-time identity
    dumped = str(matching[0].event_metadata)
    assert "WrongPassword" not in dumped


def test_logout_produces_an_audit_event(unauthenticated_client, db_session):
    email = _unique_email()
    _register(unauthenticated_client, email)
    token = _login(unauthenticated_client, email).json()["access_token"]
    unauthenticated_client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})

    user = db_session.query(User).filter(User.email == email).one()
    actions = {
        row.action
        for row in db_session.query(AuditLog).filter(AuditLog.user_id == user.id).all()
    }
    assert "auth.logout" in actions
