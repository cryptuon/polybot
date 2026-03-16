"""API authentication module for PolyBot.

Provides JWT token and API key authentication for securing API endpoints.
"""

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from polybot.config import get_settings


logger = logging.getLogger(__name__)

# Security schemes
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)


class TokenData(BaseModel):
    """JWT token payload data."""

    sub: str  # Subject (user identifier)
    exp: datetime  # Expiration time
    iat: datetime  # Issued at
    scopes: list[str] = []  # Permission scopes


class AuthResult(BaseModel):
    """Authentication result."""

    authenticated: bool
    user_id: Optional[str] = None
    method: Optional[str] = None  # "jwt" or "api_key"
    error: Optional[str] = None


def hash_api_key(api_key: str) -> str:
    """Hash an API key using SHA256.

    Args:
        api_key: The raw API key

    Returns:
        SHA256 hash of the key
    """
    return hashlib.sha256(api_key.encode()).hexdigest()


def generate_api_key() -> tuple[str, str]:
    """Generate a new API key.

    Returns:
        Tuple of (raw_key, hashed_key)
    """
    raw_key = f"pb_{secrets.token_urlsafe(32)}"
    hashed_key = hash_api_key(raw_key)
    return raw_key, hashed_key


def verify_api_key(api_key: str) -> bool:
    """Verify an API key against stored hashes.

    Args:
        api_key: The API key to verify

    Returns:
        True if valid, False otherwise
    """
    settings = get_settings()

    if not settings.auth.api_keys_hash:
        return False

    # Get list of valid key hashes
    valid_hashes = [
        h.strip() for h in settings.auth.api_keys_hash.split(",") if h.strip()
    ]

    # Hash the provided key and check against valid hashes
    provided_hash = hash_api_key(api_key)
    return provided_hash in valid_hashes


def create_jwt_token(
    user_id: str, scopes: Optional[list[str]] = None, expires_delta: Optional[timedelta] = None
) -> str:
    """Create a JWT token.

    Args:
        user_id: User identifier to encode in token
        scopes: Permission scopes
        expires_delta: Custom expiration time

    Returns:
        Encoded JWT token string

    Raises:
        HTTPException: If JWT secret is not configured
    """
    settings = get_settings()

    if not settings.auth.jwt_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JWT secret not configured",
        )

    # Import jose here to make it optional
    try:
        from jose import jwt
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JWT library not installed. Run: pip install python-jose[cryptography]",
        )

    now = datetime.now(timezone.utc)
    expire = now + (
        expires_delta or timedelta(minutes=settings.auth.jwt_expire_minutes)
    )

    payload = {
        "sub": user_id,
        "exp": expire,
        "iat": now,
        "scopes": scopes or [],
    }

    return jwt.encode(payload, settings.auth.jwt_secret, algorithm=settings.auth.jwt_algorithm)


def verify_jwt_token(token: str) -> TokenData:
    """Verify and decode a JWT token.

    Args:
        token: JWT token string

    Returns:
        TokenData with decoded payload

    Raises:
        HTTPException: If token is invalid or expired
    """
    settings = get_settings()

    if not settings.auth.jwt_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JWT secret not configured",
        )

    try:
        from jose import JWTError, jwt
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JWT library not installed",
        )

    try:
        payload = jwt.decode(
            token,
            settings.auth.jwt_secret,
            algorithms=[settings.auth.jwt_algorithm],
        )
        return TokenData(
            sub=payload["sub"],
            exp=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
            iat=datetime.fromtimestamp(payload["iat"], tz=timezone.utc),
            scopes=payload.get("scopes", []),
        )
    except JWTError as e:
        logger.warning(f"JWT verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def authenticate_request(
    request: Request,
    api_key: Optional[str] = Depends(api_key_header),
    bearer: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> AuthResult:
    """Authenticate a request using API key or JWT token.

    Args:
        request: FastAPI request object
        api_key: API key from header
        bearer: Bearer token from header

    Returns:
        AuthResult with authentication status
    """
    settings = get_settings()

    # Skip authentication if disabled
    if not settings.auth.enabled:
        return AuthResult(authenticated=True, user_id="anonymous", method="disabled")

    # Try API key authentication
    if api_key:
        if verify_api_key(api_key):
            logger.debug(f"API key authentication successful from {request.client.host}")
            return AuthResult(
                authenticated=True,
                user_id=f"apikey:{hash_api_key(api_key)[:8]}",
                method="api_key",
            )
        else:
            logger.warning(f"Invalid API key from {request.client.host}")
            return AuthResult(authenticated=False, error="Invalid API key")

    # Try JWT authentication
    if bearer:
        try:
            token_data = verify_jwt_token(bearer.credentials)
            logger.debug(f"JWT authentication successful for {token_data.sub}")
            return AuthResult(
                authenticated=True,
                user_id=token_data.sub,
                method="jwt",
            )
        except HTTPException as e:
            return AuthResult(authenticated=False, error=e.detail)

    return AuthResult(authenticated=False, error="No authentication provided")


async def require_auth(
    auth_result: AuthResult = Depends(authenticate_request),
) -> str:
    """Dependency that requires authentication.

    Use this in route dependencies to require authentication.

    Returns:
        User ID of authenticated user

    Raises:
        HTTPException: If not authenticated
    """
    if not auth_result.authenticated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=auth_result.error or "Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return auth_result.user_id or "unknown"


async def optional_auth(
    auth_result: AuthResult = Depends(authenticate_request),
) -> Optional[str]:
    """Dependency for optional authentication.

    Use this when authentication is optional but you want to know who's calling.

    Returns:
        User ID if authenticated, None otherwise
    """
    if auth_result.authenticated:
        return auth_result.user_id
    return None
