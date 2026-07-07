from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from hiresense.identity.api.cookies import resolve_session_cookie_config
from hiresense.identity.domain import AuthService

# auto_error=False so a missing Authorization header does NOT 401 on its own —
# the session may instead be carried by the httpOnly cookie, which we read as a
# fallback in _extract_token.
security = HTTPBearer(auto_error=False)


def get_auth_service(request: Request) -> AuthService | None:
    """The identity provider's auth service, or None when identity isn't wired
    (bare test apps hitting an authed route without a token). Kept as its own
    dependency so tests can override it via app.dependency_overrides."""
    identity = getattr(request.app.state, "identity", None)
    return identity.get_auth_service() if identity is not None else None


def _extract_token(
    request: Request, credentials: HTTPAuthorizationCredentials | None
) -> str | None:
    """Prefer the `Authorization: Bearer` header (API tooling / tests), then fall
    back to the httpOnly session cookie the SPA relies on."""
    if credentials is not None:
        return credentials.credentials
    cookie_config = resolve_session_cookie_config(request)
    return request.cookies.get(cookie_config.name)


def _authenticate(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
    auth_service: AuthService | None,
) -> dict[str, Any]:
    """Validate the session token from the bearer header or the httpOnly cookie.
    A missing token or unwired auth service is a 401 (not authenticated)."""
    token = _extract_token(request, credentials)
    payload = auth_service.validate_token(token) if (auth_service and token) else None
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return payload


def require_auth(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    auth_service: Annotated[AuthService | None, Depends(get_auth_service)],
) -> str:
    return _authenticate(request, credentials, auth_service)["sub"]


def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    auth_service: Annotated[AuthService | None, Depends(get_auth_service)],
) -> dict[str, Any]:
    return _authenticate(request, credentials, auth_service)


def enforce_expensive_rate_limit(request: Request) -> None:
    """Per-client-IP sliding-window limit for LLM/network-heavy endpoints.

    No-ops when no limiter is wired on app.state (bare test apps, or
    RATE_LIMIT_ENABLED=false).
    """
    limiter = getattr(request.app.state, "rate_limiter", None)
    if limiter is None:
        return
    key = request.client.host if request.client else "unknown"
    if not limiter.allow(key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded for expensive operations",
            headers={"Retry-After": str(int(limiter.window_seconds))},
        )


def require_admin(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    auth_service: Annotated[AuthService | None, Depends(get_auth_service)],
) -> dict[str, Any]:
    payload = _authenticate(request, credentials, auth_service)
    if payload.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return payload
