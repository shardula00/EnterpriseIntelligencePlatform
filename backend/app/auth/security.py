"""Password hashing (Argon2id) and JWT issuance/verification.

Framework-agnostic on purpose - no FastAPI imports here, so this is
directly unit-testable without a running app (see tests/auth/test_security.py).
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.auth.errors import InvalidTokenError
from app.config import Settings

# Argon2id (PasswordHasher's default variant) is OWASP's current recommended
# default for new applications, ahead of bcrypt/PBKDF2.
_hasher = PasswordHasher()


def hash_password(plain_password: str) -> str:
    return _hasher.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """True if `plain_password` matches `password_hash`. Never raises -
    any malformed/mismatched hash is just a failed verification."""
    try:
        return _hasher.verify(password_hash, plain_password)
    except (VerifyMismatchError, InvalidHashError):
        return False


@dataclass
class DecodedToken:
    user_id: uuid.UUID
    token_version: int


def create_access_token(user_id: uuid.UUID, token_version: int, settings: Settings) -> str:
    """Issue a JWT. Claims are deliberately minimal - see module docstring
    in app/auth/dependencies.py for why nothing beyond identity + the
    revocation counter is ever embedded here."""
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "tv": token_version,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expires_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str, settings: Settings) -> DecodedToken:
    """Decode and structurally validate a JWT. Raises InvalidTokenError for
    any bad signature, expiry, or malformed payload - callers don't need to
    know which."""
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise InvalidTokenError("Invalid or expired token.") from exc

    try:
        user_id = uuid.UUID(payload["sub"])
        token_version = int(payload["tv"])
    except (KeyError, ValueError, TypeError) as exc:
        raise InvalidTokenError("Malformed token payload.") from exc

    return DecodedToken(user_id=user_id, token_version=token_version)
