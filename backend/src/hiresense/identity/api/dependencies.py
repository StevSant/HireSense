from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from hiresense.identity.services import AuthService

security = HTTPBearer()


def get_auth_service() -> AuthService:
    raise NotImplementedError("Must be overridden during app startup via dependency_overrides")


def require_auth(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> str:
    payload = auth_service.validate_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return payload["sub"]
