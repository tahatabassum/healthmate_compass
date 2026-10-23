"""
Security and JWT verification for HealthMate Compass backend.
Extracts and validates Supabase JWT from Authorization Bearer headers.
"""
from typing import Optional, Dict, Any
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from app.core.config import settings
from app.core.supabase import get_supabase_admin
import logging

logger = logging.getLogger(__name__)

security_bearer = HTTPBearer(auto_error=False)


class AuthUser:
    """Represents an authenticated Supabase user."""
    def __init__(self, user_id: str, email: Optional[str] = None, role: str = "authenticated"):
        self.id = user_id
        self.email = email
        self.role = role

    def __repr__(self) -> str:
        return f"<AuthUser id={self.id} email={self.email}>"


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
) -> AuthUser:
    """
    FastAPI dependency to authenticate requests using Supabase JWT.
    Raises HTTPException(401) on missing or invalid token.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    # Method 1: Local JWT secret verification if SUPABASE_JWT_SECRET is configured
    if settings.SUPABASE_JWT_SECRET:
        try:
            payload: Dict[str, Any] = jwt.decode(
                token,
                settings.SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                options={"verify_aud": False},
            )
            user_id = payload.get("sub")
            if not user_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token claims: sub missing",
                )
            return AuthUser(
                user_id=user_id,
                email=payload.get("email"),
                role=payload.get("role", "authenticated"),
            )
        except JWTError as e:
            logger.warning(f"JWT decode error: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # In development, permit mock token 'dev-user-' for fast local testing and test suite
    if settings.ENVIRONMENT == "development" and token.startswith("dev-user-"):
        uid = token.replace("dev-user-", "")
        if len(uid) < 30:
            uid = "ce39d87a-0ca0-4cee-ac92-ee70803b7a81"
        return AuthUser(user_id=uid, email="dev@healthmate.local")

    # Method 2: Verify via Supabase Auth API
    supabase = get_supabase_admin()
    if supabase is not None:
        try:
            user_response = supabase.auth.get_user(token)
            if user_response and user_response.user:
                u = user_response.user
                return AuthUser(user_id=u.id, email=u.email, role=u.role or "authenticated")
        except Exception as e:
            logger.warning(f"Supabase auth verification failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired authentication session",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # If unconfigured and not in dev mock
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication service unconfigured or token invalid",
        headers={"WWW-Authenticate": "Bearer"},
    )
