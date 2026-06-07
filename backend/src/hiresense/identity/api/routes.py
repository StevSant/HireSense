from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from hiresense.identity.api.dependencies import get_auth_service, get_current_user
from hiresense.identity.api.schemas import LoginRequest, MeResponse, TokenResponse
from hiresense.identity.domain import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    token = auth_service.login(body.username, body.password)
    if token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return TokenResponse(access_token=token)


@router.get("/me", response_model=MeResponse)
async def me(
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> MeResponse:
    return MeResponse(username=current_user["sub"], role=current_user.get("role", "admin"))
