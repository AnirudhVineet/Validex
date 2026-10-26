"""Password hashing, JWT creation / decoding and login."""
from datetime import timedelta

import bcrypt
import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import User
from app.models.base import utcnow
from app.services import audit


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(user: User) -> str:
    expires = utcnow() + timedelta(minutes=settings.jwt_expire_minutes)
    claims = {"sub": user.id, "role": user.role.value, "exp": expires}
    return jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Raises jwt.InvalidTokenError if the token is invalid or expired."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def authenticate(db: Session, email: str, password: str) -> User | None:
    """Return the user if the credentials are valid. Logs success and failure to the audit chain."""
    user = db.execute(select(User).where(User.email == email.lower())).scalar_one_or_none()
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        audit.log(db, audit.SYSTEM_ACTOR, "user.login_failed", "user", audit.mask(email) or "", {})
        db.commit()
        return None
    audit.log(db, user.id, "user.login", "user", user.id, {"role": user.role.value})
    db.commit()
    return user
