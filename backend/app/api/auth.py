"""Authentication API: register, login, logout, current user.

Thin HTTP layer only - identity logic lives in app/auth/service.py,
permission resolution in app/rbac/service.py, audit recording in
app/audit/service.py.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.audit.service import AuditAction, record_event
from app.auth import service
from app.auth.dependencies import get_current_active_user, get_current_user
from app.auth.errors import EmailAlreadyRegisteredError, InactiveUserError, InvalidCredentialsError
from app.auth.schemas import LoginRequest, RegisterRequest, TokenResponse, UserOut
from app.auth.security import create_access_token
from app.config import Settings, get_settings
from app.db import get_db
from app.models.user import User
from app.rbac.service import effective_permissions

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _to_user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        created_at=user.created_at,
        roles=sorted(r.name for r in user.roles),
        permissions=sorted(effective_permissions(user)),
    )


@router.post("/register", response_model=UserOut, status_code=201)
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)) -> UserOut:
    try:
        user = service.register_user(
            db, email=payload.email, password=payload.password, full_name=payload.full_name
        )
    except EmailAlreadyRegisteredError as exc:
        # Revealing "this email is taken" at registration time (unlike at
        # login) is standard practice - the alternative is a confusing
        # signup flow that silently does nothing for an existing email.
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    record_event(
        db,
        user_id=user.id,
        action=AuditAction.USER_REGISTERED,
        resource_type="user",
        resource_id=str(user.id),
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    db.refresh(user)
    return _to_user_out(user)


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    try:
        user = service.authenticate_user(db, email=payload.email, password=payload.password)
    except InvalidCredentialsError as exc:
        record_event(
            db,
            user_id=None,
            action=AuditAction.LOGIN_FAILED,
            resource_type="user",
            metadata={"attempted_email": payload.email},
            ip_address=_client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
        db.commit()
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except InactiveUserError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    token = create_access_token(user.id, user.token_version, settings)

    record_event(
        db,
        user_id=user.id,
        action=AuditAction.LOGIN_SUCCESS,
        resource_type="user",
        resource_id=str(user.id),
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_active_user)) -> UserOut:
    return _to_user_out(current_user)


@router.post("/logout", status_code=204)
def logout(
    request: Request,
    # get_current_user, not get_current_active_user: an already-deactivated
    # user must still be able to invalidate their own token.
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    service.logout(db, current_user)
    record_event(
        db,
        user_id=current_user.id,
        action=AuditAction.LOGOUT,
        resource_type="user",
        resource_id=str(current_user.id),
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
