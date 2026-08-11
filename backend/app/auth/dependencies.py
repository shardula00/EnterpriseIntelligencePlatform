"""FastAPI dependencies for identifying the current user from a JWT.

Claims are deliberately minimal (`sub`, `tv`, `iat`, `exp` - see
security.py) - no email, name, roles, or permissions ever go in the token.
Two reasons: (1) a JWT is base64, not encrypted - anything in it is
readable by whoever holds the token; (2) roles/permissions can change
between token issuance and use, so baking them in would let a revoked
permission keep working until the token expires. Re-checking against the
DB on every request (which we're already doing to load the user) keeps
authorization always current.
"""

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth import security
from app.auth.errors import InvalidTokenError
from app.config import Settings, get_settings
from app.db import get_db
from app.models.user import User

# auto_error=False so a missing header raises our own 401 with a
# consistent message, rather than FastAPI's default.
_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated.")

    try:
        decoded = security.decode_access_token(credentials.credentials, settings)
    except InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    user = db.get(User, decoded.user_id)
    if user is None or user.token_version != decoded.token_version:
        # Covers: user deleted, logged out (token_version bumped), or an
        # admin deactivated them and that also bumped the version.
        raise HTTPException(
            status_code=401, detail="Token has been invalidated. Please log in again."
        )

    return user


def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """Same as get_current_user, but also rejects deactivated accounts.

    401, not 403: this is about whether the credential/identity is usable
    at all, not about whether it has permission for a specific action.
    """
    if not current_user.is_active:
        raise HTTPException(status_code=401, detail="This account has been deactivated.")
    return current_user
