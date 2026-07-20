from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from hiresense.identity.api.cookies import (
    clear_session_cookie,
    resolve_session_cookie_config,
    set_session_cookie,
)
from hiresense.identity.api.dependencies import (
    enforce_login_rate_limit,
    get_auth_service,
    get_current_user,
)
from hiresense.identity.api.schemas import LoginRequest, LogoutResponse, MeResponse, TokenResponse
from hiresense.identity.domain import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


# Rate-limited: login is the brute-force surface for the single admin
# credential, so it has its own stricter per-client-IP limiter, independent of
# the shared expensive-operations bucket.
@router.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[Depends(enforce_login_rate_limit)],
)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    auth_service: Annotated[AuthService | None, Depends(get_auth_service)],
) -> TokenResponse:
    if auth_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Identity not configured"
        )
    token = auth_service.login(body.username, body.password)
    if token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    # Primary session transport: the httpOnly cookie (XSS can't read it). The
    # token is also returned in the body so API tooling/tests can use the
    # `Authorization: Bearer` fallback the auth dependency still accepts.
    set_session_cookie(response, resolve_session_cookie_config(request), token)
    return TokenResponse(access_token=token)


@router.post("/logout", response_model=LogoutResponse)
async def logout(request: Request, response: Response) -> LogoutResponse:
    # Server-side clear so the browser drops the httpOnly cookie it can't touch
    # from JS. No auth required: logging out an already-invalid session is a no-op.
    clear_session_cookie(response, resolve_session_cookie_config(request))
    return LogoutResponse()


@router.get("/me", response_model=MeResponse)
async def me(
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> MeResponse:
    return MeResponse(username=current_user["sub"], role=current_user.get("role", "admin"))
