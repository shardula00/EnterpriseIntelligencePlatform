"""Registration, authentication, and logout - pure DB logic, no HTTP.

Every function here takes a `Session` and raises a plain `AuthError`
subclass on failure; app/api/auth.py maps those onto HTTP status codes.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import security
from app.auth.errors import EmailAlreadyRegisteredError, InactiveUserError, InvalidCredentialsError
from app.models.user import Role, User

# New self-registrations get the least-privileged role by default. An admin
# can promote them later via the user-management API - registration itself
# can never grant elevated access, which is what keeps self-registration
# safe to leave open.
DEFAULT_REGISTRATION_ROLE = "VIEWER"


def register_user(db: Session, *, email: str, password: str, full_name: str) -> User:
    existing = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if existing is not None:
        raise EmailAlreadyRegisteredError(f"An account with email '{email}' already exists.")

    user = User(
        email=email,
        password_hash=security.hash_password(password),
        full_name=full_name,
    )

    default_role = db.execute(
        select(Role).where(Role.name == DEFAULT_REGISTRATION_ROLE)
    ).scalar_one_or_none()
    if default_role is not None:
        user.roles = [default_role]

    db.add(user)
    db.flush()  # assign user.id without committing yet - caller controls the transaction
    return user


def authenticate_user(db: Session, *, email: str, password: str) -> User:
    """Raises InvalidCredentialsError for either a wrong email or wrong
    password (same exception for both - see errors.py for why), and
    InactiveUserError only once the password has already been verified
    correct, so a deactivated account's existence isn't leaked to anyone
    who doesn't already know its password."""
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is None or not security.verify_password(password, user.password_hash):
        raise InvalidCredentialsError("Incorrect email or password.")

    if not user.is_active:
        raise InactiveUserError("This account has been deactivated.")

    return user


def get_user_by_id(db: Session, user_id: uuid.UUID) -> User | None:
    return db.get(User, user_id)


def logout(db: Session, user: User) -> None:
    """Invalidates every previously-issued token for this user by bumping
    token_version - see app/auth/security.py's claims and
    app/auth/dependencies.py's verification for how this is enforced."""
    user.token_version += 1
    db.flush()
