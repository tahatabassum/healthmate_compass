"""
Security and JWT verification for HealthMate Compass backend.
Supports asymmetric Supabase JWTs (ES256/RS256) via cached JWKS endpoint,
legacy HS256 secret verification, and authoritative fallback via Supabase Auth API.
"""
from typing import Optional, Dict, Any, List
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from jwt import PyJWKClient, PyJWKClientError, ExpiredSignatureError, InvalidTokenError
from jose import jwt as jose_jwt, JWTError as JoseJWTError
from app.core.config import settings
from app.core.supabase import get_supabase_admin
import logging

logger = logging.getLogger("healthmate.security")

security_bearer = HTTPBearer(auto_error=False)

_jwks_client: Optional[PyJWKClient] = None


def get_jwks_client() -> Optional[PyJWKClient]:
    """Returns a singleton PyJWKClient with in-memory key caching."""
    global _jwks_client
    if _jwks_client is not None:
        return _jwks_client

    if not settings.SUPABASE_URL:
        return None

    try:
        jwks_url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"
        _jwks_client = PyJWKClient(
            jwks_url,
            cache_keys=True,
            max_cached_keys=16,
            lifespan=3600,  # Cache public keys for 1 hour
        )
        return _jwks_client
    except Exception as e:
        logger.warning("Failed to initialize JWKS client [%s]: %s", type(e).__name__, e)
        return None


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
    
    Verification order:
    1. Development mock token (development environment only)
    2. Cached JWKS endpoint (supports modern Supabase ES256 / RS256 asymmetric keys)
    3. Legacy HS256 secret (if SUPABASE_JWT_SECRET is configured)
    4. Supabase Auth API fallback (supabase.auth.get_user(token))
    
    Raises 401 with informative, safe diagnostic detail if unconfigured or invalid.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials.strip()

    # 1. In development, permit mock token 'dev-user-' for fast local testing
    if settings.ENVIRONMENT == "development" and token.startswith("dev-user-"):
        uid = token.replace("dev-user-", "").strip()
        if len(uid) < 30:
            uid = "ce39d87a-0ca0-4cee-ac92-ee70803b7a81"
        return AuthUser(user_id=uid, email="dev@healthmate.local", role="authenticated")

    # Diagnostic check: verify whether auth backend is configured
    configured_vars: List[str] = []
    missing_vars: List[str] = []
    for var_name, val in [
        ("SUPABASE_URL", settings.SUPABASE_URL),
        ("SUPABASE_ANON_KEY", settings.SUPABASE_ANON_KEY),
        ("SUPABASE_SERVICE_ROLE_KEY", settings.SUPABASE_SERVICE_ROLE_KEY),
    ]:
        if val:
            configured_vars.append(var_name)
        else:
            missing_vars.append(var_name)

    if not settings.SUPABASE_URL and not settings.SUPABASE_JWT_SECRET:
        logger.error(
            "Authentication unconfigured: missing required variables: %s",
            missing_vars,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication service unconfigured (missing required environment variables: {', '.join(missing_vars)})",
            headers={"WWW-Authenticate": "Bearer"},
        )

    last_verification_error: Optional[str] = None
    last_error_type: Optional[str] = None

    # 2. Method A: Asymmetric JWKS verification (cached in memory)
    jwks_client = get_jwks_client()
    if jwks_client:
        try:
            signing_key = jwks_client.get_signing_key_from_jwt(token)
            payload: Dict[str, Any] = jwt.decode(
                token,
                signing_key.key,
                algorithms=["ES256", "RS256", "HS256"],
                options={"verify_aud": False, "verify_exp": True},
            )
            user_id = payload.get("sub")
            if user_id:
                return AuthUser(
                    user_id=user_id,
                    email=payload.get("email"),
                    role=payload.get("role", "authenticated"),
                )
            last_verification_error = "Token payload missing 'sub' claim"
            last_error_type = "InvalidClaimsError"
        except ExpiredSignatureError as e:
            logger.warning("Token expired [%s]: %s", type(e).__name__, e)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication token has expired. Please refresh your session.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except (InvalidTokenError, PyJWKClientError) as e:
            last_error_type = type(e).__name__
            last_verification_error = str(e)
            logger.debug("JWKS verification failed [%s]: %s (trying fallbacks)", last_error_type, e)
        except Exception as e:
            last_error_type = type(e).__name__
            last_verification_error = str(e)
            logger.debug("Unexpected error during JWKS decode [%s]: %s", last_error_type, e)

    # 3. Method B: Legacy HS256 secret verification (if SUPABASE_JWT_SECRET configured)
    if settings.SUPABASE_JWT_SECRET:
        try:
            payload = jose_jwt.decode(
                token,
                settings.SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                options={"verify_aud": False},
            )
            user_id = payload.get("sub")
            if user_id:
                return AuthUser(
                    user_id=user_id,
                    email=payload.get("email"),
                    role=payload.get("role", "authenticated"),
                )
        except JoseJWTError as e:
            last_error_type = type(e).__name__
            last_verification_error = str(e)
            logger.debug("HS256 secret verification failed [%s]: %s", last_error_type, e)

    # 4. Method C: Authoritative fallback via Supabase Auth API
    supabase = get_supabase_admin()
    if supabase is not None:
        try:
            user_response = supabase.auth.get_user(token)
            if user_response and user_response.user:
                u = user_response.user
                return AuthUser(user_id=u.id, email=u.email, role=u.role or "authenticated")
        except Exception as e:
            last_error_type = type(e).__name__
            last_verification_error = str(e)
            logger.warning("Supabase auth.get_user verification failed [%s]: %s", last_error_type, e)

    # If verification failed across all configured methods
    logger.warning(
        "Authentication failed: token rejected. ExceptionType=%s, Reason=%s, ConfiguredVars=%s",
        last_error_type or "Unknown",
        last_verification_error or "Token signature could not be verified",
        configured_vars,
    )
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )

