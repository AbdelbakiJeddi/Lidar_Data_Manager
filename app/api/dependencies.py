"""API dependencies for FastAPI dependency injection."""
import logging
from typing import AsyncGenerator
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorDatabase
from minio import Minio
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.auth import decode_access_token, is_jwt_error
from app.core.minio_client import get_minio_client
from app.core.mongo_client import get_database

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)


async def get_db() -> AsyncGenerator[AsyncIOMotorDatabase, None]:
    """Dependency to get MongoDB database instance."""
    db = await get_database()
    try:
        yield db
    finally:
        pass  # Connection managed by motor client pool


def get_minio() -> Minio:
    """Dependency to get MinIO client instance."""
    return get_minio_client()


class CurrentUser(BaseModel):
    """Authenticated user context."""

    username: str
    role: str


def _unauthorized(detail: str = "Not authenticated") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> CurrentUser:
    """Validate bearer token and return auth context."""
    if not credentials:
        raise _unauthorized()

    try:
        payload = decode_access_token(credentials.credentials)
    except Exception as exc:
        if is_jwt_error(exc):
            raise _unauthorized("Invalid or expired token") from exc
        raise

    username = payload.get("sub")
    role = payload.get("role")
    if not username or not role:
        raise _unauthorized("Invalid token payload")

    return CurrentUser(username=username, role=role)


def require_admin(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """Ensure current user has admin privileges."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return current_user
