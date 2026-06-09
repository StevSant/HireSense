from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from hiresense.identity.domain import AuthService

security = HTTPBearer()


def get_auth_service(request: Request) -> AuthService:
    return request.app.state.identity.get_auth_service()


def require_auth(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> str:
    payload = auth_service.validate_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return payload["sub"]


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> dict[str, Any]:
    payload = auth_service.validate_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return payload


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
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> dict[str, Any]:
    payload = auth_service.validate_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    if payload.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return payload
