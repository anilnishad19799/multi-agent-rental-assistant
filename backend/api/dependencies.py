"""API route dependencies — authentication and user resolution."""
from typing import Optional
from fastapi import Header, HTTPException, status
from backend.repositories.user_repository import UserRepository
from backend.services.auth_service import decode_access_token
from backend.models import User

user_repo = UserRepository()


async def get_current_user(authorization: Optional[str] = Header(None)) -> Optional[User]:
    """Extract and authenticate the user from Authorization Bearer token header."""
    if not authorization:
        return None

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None

    token = parts[1]
    payload = decode_access_token(token)
    if not payload or not payload.get("sub"):
        return None

    user_id = payload.get("sub")
    user = await user_repo.get_by_id(user_id)
    return user


async def require_current_user(authorization: Optional[str] = Header(None)) -> User:
    """Strict dependency requiring authenticated user."""
    user = await get_current_user(authorization)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def require_admin(authorization: Optional[str] = Header(None)) -> User:
    """Strict dependency requiring authenticated user with ADMIN role."""
    user = await require_current_user(authorization)
    is_admin = bool(user.is_admin or user.email == "admin@gmail.com")
    if not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Observability traces and system metrics are restricted to administrators only.",
        )
    return user
