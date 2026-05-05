"""Authentication API routes."""

from fastapi import APIRouter, HTTPException, status

from app.core.auth import create_access_token, verify_credentials
from app.models import LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest) -> TokenResponse:
    """Authenticate a user and return a JWT."""
    result = verify_credentials(request.username, request.password)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    username, role = result
    token = create_access_token(subject=username, role=role)
    return TokenResponse(access_token=token)
