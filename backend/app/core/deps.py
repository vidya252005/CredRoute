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


def require_admin(user: User | None = Depends(get_current_user)) -> User:
    if not user:
        raise AppError("UNAUTHENTICATED", "Authentication required.", 401)
    if user.role != UserRole.admin:
        raise AppError("FORBIDDEN", "Admin access required.", 403)
    return user
