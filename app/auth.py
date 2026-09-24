from fastapi import Depends, Request
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(raw: str) -> str:
    return pwd_context.hash(raw)


def verify_password(raw: str, hashed: str) -> bool:
    return pwd_context.verify(raw, hashed)


class NotAuthenticated(Exception):
    """Raised by get_current_user; an exception handler turns it into a redirect."""
    pass


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """FastAPI dependency. Reads the signed session cookie, loads that User row.
    This single object is what every protected route gets handed for free."""
    user_id = request.session.get("user_id")
    if not user_id:
        raise NotAuthenticated()
    user = db.get(User, user_id)
    if not user:
        raise NotAuthenticated()
    return user