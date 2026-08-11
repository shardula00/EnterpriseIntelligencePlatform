"""Integration tests for app/rbac/service.py, against a live Postgres."""

import uuid

import pytest
from sqlalchemy import select

from app.auth.security import hash_password
from app.models.user import Role, User
from app.rbac import service
from app.rbac.errors import RoleNotFoundError, SelfModificationError


def _unique_email() -> str:
    return f"rbac-test-{uuid.uuid4().hex[:8]}@example.com"


def _make_user(db_session, role_names: list[str]) -> User:
    roles = list(db_session.execute(select(Role).where(Role.name.in_(role_names))).scalars())
    user = User(
        email=_unique_email(),
        password_hash=hash_password("Password123"),
        full_name="RBAC Test User",
        roles=roles,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_effective_permissions_for_viewer(db_session):
    user = _make_user(db_session, ["VIEWER"])
    assert service.effective_permissions(user) == {"dataset:read", "dashboard:read", "ml:read"}


def test_effective_permissions_for_analyst(db_session):
    user = _make_user(db_session, ["ANALYST"])
    assert service.effective_permissions(user) == {
        "dataset:read",
        "dataset:create",
        "dashboard:read",
        "dashboard:configure",
        "ml:read",
        "ml:train",
        "ml:predict",
    }


def test_analyst_does_not_have_dataset_delete(db_session):
    user = _make_user(db_session, ["ANALYST"])
    assert not service.has_permission(user, "dataset:delete")


def test_admin_has_every_permission(db_session):
    user = _make_user(db_session, ["ADMIN"])
    all_permissions = {p.name for p in service.list_permissions(db_session)}
    assert service.effective_permissions(user) == all_permissions


def test_effective_permissions_is_the_union_across_multiple_roles(db_session):
    # A user with both VIEWER and ANALYST roles should get the union, with
    # no duplicates and nothing lost.
    user = _make_user(db_session, ["VIEWER", "ANALYST"])
    assert service.effective_permissions(user) == {
        "dataset:read",
        "dataset:create",
        "dashboard:read",
        "dashboard:configure",
        "ml:read",
        "ml:train",
        "ml:predict",
    }


def test_user_with_no_roles_has_no_permissions(db_session):
    user = _make_user(db_session, [])
    assert service.effective_permissions(user) == set()


def test_assign_roles_replaces_existing_assignment(db_session):
    admin = _make_user(db_session, ["ADMIN"])
    target = _make_user(db_session, ["VIEWER"])

    service.assign_roles(db_session, current_user=admin, target_user=target, role_names=["ANALYST"])
    db_session.commit()

    assert [r.name for r in target.roles] == ["ANALYST"]


def test_assign_roles_rejects_unknown_role_name(db_session):
    admin = _make_user(db_session, ["ADMIN"])
    target = _make_user(db_session, ["VIEWER"])

    with pytest.raises(RoleNotFoundError):
        service.assign_roles(
            db_session, current_user=admin, target_user=target, role_names=["SUPERUSER"]
        )


def test_assign_roles_rejects_self_modification(db_session):
    admin = _make_user(db_session, ["ADMIN"])

    with pytest.raises(SelfModificationError):
        service.assign_roles(
            db_session, current_user=admin, target_user=admin, role_names=["VIEWER"]
        )


def test_update_user_rejects_self_deactivation(db_session):
    admin = _make_user(db_session, ["ADMIN"])

    with pytest.raises(SelfModificationError):
        service.update_user(db_session, current_user=admin, target_user=admin, is_active=False)


def test_update_user_deactivation_bumps_token_version(db_session):
    admin = _make_user(db_session, ["ADMIN"])
    target = _make_user(db_session, ["VIEWER"])
    original_version = target.token_version

    service.update_user(db_session, current_user=admin, target_user=target, is_active=False)
    db_session.commit()

    assert target.is_active is False
    assert target.token_version == original_version + 1


def test_update_user_full_name_does_not_require_self_check(db_session):
    # Updating one's own full_name is not a privilege change, so it's not
    # blocked by the self-modification rule (only role/active-status are).
    admin = _make_user(db_session, ["ADMIN"])

    service.update_user(db_session, current_user=admin, target_user=admin, full_name="New Name")
    db_session.commit()

    assert admin.full_name == "New Name"
