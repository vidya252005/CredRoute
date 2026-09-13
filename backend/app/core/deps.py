from fastapi import Depends, Header
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.entities import User, UserRole


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = decode_access_token(token)
        user = db.query(User).filter(User.id == int(payload["sub"])).first()
        return user
    except (JWTError, ValueError, KeyError):
        return None


def require_user(user: User | None = Depends(get_current_user)) -> User:
    if not user:
        raise AppError("UNAUTHENTICATED", "Authentication required.", 401)
    return user


def require_admin(user: User | None = Depends(get_current_user)) -> User:
    user = require_user(user)
    if user.role != UserRole.admin:
        raise AppError("FORBIDDEN", "Admin access required.", 403)
    return user


def can_view_application(user: User | None, profile) -> bool:
    if user is None:
        return False
    if user.role == UserRole.admin:
        return True
    return profile is not None and profile.user_id == user.id


def can_access_application(user: User | None, profile) -> bool:
    """Sandbox applications (no owner) stay demo-usable. Owned apps are owner/admin only."""
    if profile is None:
        return False
    if profile.user_id is None:
        return True
    return can_view_application(user, profile)


def require_application_access(user: User | None, profile) -> None:
    if can_access_application(user, profile):
        return
    if user is None:
        raise AppError("UNAUTHENTICATED", "Authentication required to access this application.", 401)
    raise AppError("FORBIDDEN", "You do not have access to this application.", 403)
