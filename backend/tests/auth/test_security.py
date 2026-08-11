"""Pure unit tests for password hashing and JWT issuance/verification.

No database, no HTTP - see tests/auth/test_api.py for the end-to-end
register/login/me/logout flow against a live Postgres.
"""

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.auth import security
from app.auth.errors import InvalidTokenError
from app.config import Settings


@pytest.fixture
def settings() -> Settings:
    # >=32 bytes, matching the length PyJWT recommends for HS256 - avoids a
    # noisy (harmless) InsecureKeyLengthWarning in test output.
    return Settings(
        jwt_secret_key="test-secret-key-at-least-32-bytes-long",
        jwt_algorithm="HS256",
        jwt_expires_minutes=60,
    )


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------


def test_hash_password_does_not_return_the_plaintext():
    hashed = security.hash_password("CorrectPassword123")
    assert hashed != "CorrectPassword123"
    assert "CorrectPassword123" not in hashed


def test_hash_password_uses_argon2():
    hashed = security.hash_password("CorrectPassword123")
    assert hashed.startswith("$argon2")


def test_verify_password_accepts_the_correct_password():
    hashed = security.hash_password("CorrectPassword123")
    assert security.verify_password("CorrectPassword123", hashed) is True


def test_verify_password_rejects_the_wrong_password():
    hashed = security.hash_password("CorrectPassword123")
    assert security.verify_password("WrongPassword456", hashed) is False


def test_verify_password_rejects_a_malformed_hash_without_raising():
    assert security.verify_password("anything", "not-a-real-hash") is False


def test_hashing_the_same_password_twice_gives_different_hashes():
    # Argon2 salts every hash - two hashes of the same password must differ.
    first = security.hash_password("CorrectPassword123")
    second = security.hash_password("CorrectPassword123")
    assert first != second


# ---------------------------------------------------------------------------
# JWT issuance/verification
# ---------------------------------------------------------------------------


def test_create_and_decode_access_token_round_trips(settings: Settings):
    user_id = uuid.uuid4()
    token = security.create_access_token(user_id, token_version=3, settings=settings)

    decoded = security.decode_access_token(token, settings)

    assert decoded.user_id == user_id
    assert decoded.token_version == 3


def test_token_claims_contain_only_sub_tv_iat_exp(settings: Settings):
    token = security.create_access_token(uuid.uuid4(), token_version=0, settings=settings)
    payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])

    assert set(payload.keys()) == {"sub", "tv", "iat", "exp"}


def test_decode_rejects_a_token_signed_with_a_different_secret(settings: Settings):
    token = security.create_access_token(uuid.uuid4(), token_version=0, settings=settings)
    wrong_settings = Settings(jwt_secret_key="a-completely-different-secret-of-32-plus-bytes")

    with pytest.raises(InvalidTokenError):
        security.decode_access_token(token, wrong_settings)


def test_decode_rejects_an_expired_token(settings: Settings):
    now = datetime.now(UTC)
    payload = {
        "sub": str(uuid.uuid4()),
        "tv": 0,
        "iat": now - timedelta(hours=2),
        "exp": now - timedelta(hours=1),  # expired an hour ago
    }
    expired_token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

    with pytest.raises(InvalidTokenError):
        security.decode_access_token(expired_token, settings)


def test_decode_rejects_garbage_input(settings: Settings):
    with pytest.raises(InvalidTokenError):
        security.decode_access_token("not.a.real.token", settings)


def test_decode_rejects_a_token_missing_required_claims(settings: Settings):
    incomplete_payload = {"sub": str(uuid.uuid4())}  # missing "tv"
    token = jwt.encode(
        incomplete_payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )

    with pytest.raises(InvalidTokenError):
        security.decode_access_token(token, settings)
