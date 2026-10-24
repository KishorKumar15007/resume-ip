from typing import Callable

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from app.core.security import decode_access_token
from app.database import SessionLocal, _trace_event
from app.models import User


bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> User:
    payload = decode_access_token(credentials.credentials)

    user_id = payload["sub"]

    # Finish the authentication query and release its connection before FastAPI
    # schedules the route function in another worker thread.
    _trace_event("auth_session_begin")
    try:
        with SessionLocal() as db:
            _trace_event("auth_query_begin")
            user = db.scalar(select(User).where(User.id == user_id))
            _trace_event("auth_query_end")
    finally:
        _trace_event("auth_session_end")

    if user is None:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def require_role(required_role: str) -> Callable:
    def role_dependency(
        current_user: User = Depends(get_current_user),
    ) -> User:
        from fastapi import HTTPException, status

        if current_user.role != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )

        return current_user

    return role_dependency
