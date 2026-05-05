"""Authentication helpers for simple role-based access control."""

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt

from app.core.settings import get_settings


def create_access_token(*, subject: str, role: str) -> str:
    """Create a signed JWT token for the given user and role."""
    settings = get_settings()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "exp": expires_at,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT token."""
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def verify_credentials(username: str, password: str) -> tuple[str, str] | None:
    """Verify username/password against the two configured users."""
    settings = get_settings()

    if username == settings.auth_admin_username and password == settings.auth_admin_password:
        return username, "admin"

    if username == settings.auth_user_username and password == settings.auth_user_password:
        return username, "user"

    return None


def is_jwt_error(exc: Exception) -> bool:
    """Return true when an exception is a JWT decoding error."""
    return isinstance(exc, JWTError)
