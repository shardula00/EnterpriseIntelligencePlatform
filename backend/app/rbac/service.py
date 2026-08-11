"""Permission resolution and admin user-management operations.

effective_permissions() is the single place "what can this user do" is
computed - the union of every permission granted by every role assigned to
them. Never cached, never stored on the token; always resolved fresh
against the current state of user_roles/role_permissions.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import Permission, Role, User
from app.rbac.errors import RoleNotFoundError, SelfModificationError, UserNotFoundError


def effective_permissions(user: User) -> set[str]:
    return {permission.name for role in user.roles for permission in role.permissions}


def has_permission(user: User, permission_name: str) -> bool:
    return permission_name in effective_permissions(user)


def list_roles(db: Session) -> list[Role]:
    return list(db.execute(select(Role).order_by(Role.name)).scalars())


def list_permissions(db: Session) -> list[Permission]:
    return list(db.execute(select(Permission).order_by(Permission.name)).scalars())


def list_users(db: Session, *, limit: int = 50, offset: int = 0) -> list[User]:
    stmt = select(User).order_by(User.created_at.desc()).limit(limit).offset(offset)
    return list(db.execute(stmt).scalars())


def get_user(db: Session, user_id: uuid.UUID) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise UserNotFoundError(f"User {user_id} not found.")
    return user


def _require_not_self(current_user: User, target_user: User) -> None:
    """The mechanism this app uses to block self-privilege-escalation: an
    admin cannot change their own role assignment or active status through
    the admin API, full stop - not "cannot increase," cannot at all. That's
    a simpler, unambiguous rule than trying to distinguish escalation from
    non-escalation changes."""
    if current_user.id == target_user.id:
        raise SelfModificationError(
            "You cannot change your own role assignment or active status."
        )


def assign_roles(
    db: Session, *, current_user: User, target_user: User, role_names: list[str]
) -> User:
    _require_not_self(current_user, target_user)

    roles = list(db.execute(select(Role).where(Role.name.in_(role_names))).scalars())
    found_names = {r.name for r in roles}
    missing = set(role_names) - found_names
    if missing:
        raise RoleNotFoundError(f"Unknown role(s): {', '.join(sorted(missing))}")

    target_user.roles = roles
    db.flush()
    return target_user


def update_user(
    db: Session,
    *,
    current_user: User,
    target_user: User,
    full_name: str | None = None,
    is_active: bool | None = None,
) -> User:
    if is_active is not None:
        _require_not_self(current_user, target_user)
        target_user.is_active = is_active
        if not is_active:
            # Deactivation must take effect immediately, not just at the
            # next natural token expiry - see User.token_version.
            target_user.token_version += 1

    if full_name is not None:
        target_user.full_name = full_name

    db.flush()
    return target_user
