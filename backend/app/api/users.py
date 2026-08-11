"""User-management API (admin). Thin HTTP layer over app/rbac/service.py.

Every route is permission-gated via require_permission(...) - see
app/rbac/dependencies.py - not by scattering role-string checks here.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.audit.service import AuditAction, record_event
from app.auth import service as auth_service
from app.auth.errors import EmailAlreadyRegisteredError
from app.auth.schemas import RegisterRequest
from app.db import get_db
from app.models.user import User
from app.rbac import service
from app.rbac.dependencies import require_permission
from app.rbac.errors import RoleNotFoundError, SelfModificationError, UserNotFoundError
from app.rbac.schemas import (
    AssignRolesRequest,
    PermissionOut,
    RoleOut,
    UpdateUserRequest,
    UserAdminOut,
)

router = APIRouter(prefix="/users", tags=["users"])

# Separate router (no /users prefix) so "/roles" and "/permissions" can
# never be mis-routed as a "/users/{user_id}" path parameter.
catalog_router = APIRouter(tags=["users"])


@catalog_router.get("/roles", response_model=list[RoleOut])
def list_roles(
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_permission("user:read")),
) -> list[RoleOut]:
    return [
        RoleOut(id=r.id, name=r.name, description=r.description) for r in service.list_roles(db)
    ]


@catalog_router.get("/permissions", response_model=list[PermissionOut])
def list_permissions(
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_permission("user:read")),
) -> list[PermissionOut]:
    return [
        PermissionOut(id=p.id, name=p.name, description=p.description)
        for p in service.list_permissions(db)
    ]


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _to_admin_out(user: User) -> UserAdminOut:
    return UserAdminOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        roles=sorted(r.name for r in user.roles),
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


def _get_or_404(db: Session, user_id: UUID) -> User:
    try:
        return service.get_user(db, user_id)
    except UserNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("", response_model=list[UserAdminOut])
def list_users(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_permission("user:read")),
) -> list[UserAdminOut]:
    return [_to_admin_out(u) for u in service.list_users(db, limit=limit, offset=offset)]


@router.get("/{user_id}", response_model=UserAdminOut)
def get_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_permission("user:read")),
) -> UserAdminOut:
    return _to_admin_out(_get_or_404(db, user_id))


@router.post("", response_model=UserAdminOut, status_code=201)
def create_user(
    payload: RegisterRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("user:create")),
) -> UserAdminOut:
    try:
        user = auth_service.register_user(
            db, email=payload.email, password=payload.password, full_name=payload.full_name
        )
    except EmailAlreadyRegisteredError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    record_event(
        db,
        user_id=current_user.id,
        action=AuditAction.USER_CREATED,
        resource_type="user",
        resource_id=str(user.id),
        metadata={"created_email": user.email},
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    db.refresh(user)
    return _to_admin_out(user)


@router.patch("/{user_id}", response_model=UserAdminOut)
def update_user(
    user_id: UUID,
    payload: UpdateUserRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("user:update")),
) -> UserAdminOut:
    target = _get_or_404(db, user_id)
    try:
        service.update_user(
            db,
            current_user=current_user,
            target_user=target,
            full_name=payload.full_name,
            is_active=payload.is_active,
        )
    except SelfModificationError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    if payload.is_active is not None:
        action = AuditAction.USER_ACTIVATED if payload.is_active else AuditAction.USER_DEACTIVATED
        record_event(
            db,
            user_id=current_user.id,
            action=action,
            resource_type="user",
            resource_id=str(target.id),
            ip_address=_client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
    if payload.full_name is not None:
        record_event(
            db,
            user_id=current_user.id,
            action=AuditAction.USER_UPDATED,
            resource_type="user",
            resource_id=str(target.id),
            metadata={"full_name": payload.full_name},
            ip_address=_client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )

    db.commit()
    db.refresh(target)
    return _to_admin_out(target)


@router.post("/{user_id}/roles", response_model=UserAdminOut)
def assign_roles(
    user_id: UUID,
    payload: AssignRolesRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("user:update")),
) -> UserAdminOut:
    target = _get_or_404(db, user_id)
    try:
        service.assign_roles(
            db, current_user=current_user, target_user=target, role_names=payload.role_names
        )
    except SelfModificationError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RoleNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    record_event(
        db,
        user_id=current_user.id,
        action=AuditAction.USER_ROLE_CHANGED,
        resource_type="user",
        resource_id=str(target.id),
        metadata={"new_roles": payload.role_names},
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    db.refresh(target)
    return _to_admin_out(target)


@router.delete("/{user_id}", status_code=204)
def delete_user(
    user_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("user:delete")),
) -> None:
    target = _get_or_404(db, user_id)
    if target.id == current_user.id:
        raise HTTPException(status_code=403, detail="You cannot delete your own account.")

    record_event(
        db,
        user_id=current_user.id,
        action=AuditAction.USER_DELETED,
        resource_type="user",
        resource_id=str(target.id),
        metadata={"deleted_email": target.email},
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    db.delete(target)
    db.commit()
