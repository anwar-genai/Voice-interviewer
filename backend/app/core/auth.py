"""Authentication: verify Supabase-issued JWTs, expose the caller's user id.

Every protected route depends on ``require_user`` (directly, or via the rate
limiter, which depends on it). Supabase owns the user store; we only verify the
access token it signs and read ``sub`` (the user's UUID).

Supabase signs access tokens one of two ways depending on project age:
  - asymmetric (ES256/RS256) verified against the project's public JWKS, or
  - legacy HS256 with the shared project JWT secret.
We route on the token's ``alg`` header so either works.
"""

from __future__ import annotations

import logging
from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import MissingConfigError, get_settings

logger = logging.getLogger("interview.auth")

# When auth is disabled for local dev, every request is this synthetic user.
DEV_USER_ID = "dev-user"

_bearer = HTTPBearer(auto_error=False)


@lru_cache(maxsize=1)
def _jwks_client() -> jwt.PyJWKClient:
    """JWKS client for the project's public signing keys (cached, self-refreshing)."""
    url = get_settings().require_supabase_url().rstrip("/")
    return jwt.PyJWKClient(f"{url}/auth/v1/.well-known/jwks.json")


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    """Return the authenticated user's id, or reject the request."""
    settings = get_settings()

    if not settings.auth_enabled:
        return DEV_USER_ID

    if creds is None:
        raise _unauthorized("Not authenticated")
    token = creds.credentials

    try:
        alg = jwt.get_unverified_header(token).get("alg")
    except jwt.PyJWTError:
        raise _unauthorized("Malformed token")

    try:
        if alg == "HS256":
            key: object = settings.require_supabase_jwt_secret()
            algorithms = ["HS256"]
        else:
            key = _jwks_client().get_signing_key_from_jwt(token).key
            algorithms = ["ES256", "RS256"]
    except MissingConfigError as exc:
        # Auth is on but the matching key material isn't configured: a server fault.
        logger.error("Cannot verify tokens: %s", exc)
        raise HTTPException(status_code=500, detail="Authentication is not configured")

    try:
        payload = jwt.decode(token, key, algorithms=algorithms, audience="authenticated")
    except jwt.PyJWTError as exc:
        logger.info("Rejected token: %s", exc)
        raise _unauthorized("Invalid or expired token")

    user_id = payload.get("sub")
    if not user_id:
        raise _unauthorized("Malformed token")
    return user_id
