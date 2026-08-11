"""The require_permission(...) dependency factory.

Used as `Depends(require_permission("dataset:delete"))` on a route instead
of scattering `if current_user.role == ...` checks through handlers - one
reusable authorization check, expressed declaratively at the route.
"""

from collections.abc import Callable

from fastapi import Depends, HTTPException

from app.auth.dependencies import get_current_active_user
from app.models.user import User
from app.rbac.service import has_permission


def require_permission(permission_name: str) -> Callable[..., User]:
    def dependency(current_user: User = Depends(get_current_active_user)) -> User:
        if not has_permission(current_user, permission_name):
            raise HTTPException(
                status_code=403, detail=f"Missing required permission: {permission_name}"
            )
        return current_user

    return dependency
