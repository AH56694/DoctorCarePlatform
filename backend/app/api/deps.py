from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session, selectinload

from backend.app.db.models import User
from backend.app.db.session import get_db
from backend.app.services.auth import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = decode_access_token(credentials.credentials)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = (
        db.query(User)
        .options(selectinload(User.roles))
        .filter(User.id == user_id)
        .first()
    )
    if not user or user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is unavailable",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_roles(*allowed_roles: str) -> Callable[..., User]:
    allowed = set(allowed_roles)

    def dependency(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        actual = {role.role for role in current_user.roles}
        if (
            current_user.active_role not in allowed
            or current_user.active_role not in actual
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required role: {', '.join(sorted(allowed))}",
            )
        return current_user

    return dependency


require_admin_user = require_roles("admin")
