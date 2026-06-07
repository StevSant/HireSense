from __future__ import annotations

from typing import Any

import pytest
from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials

from hiresense.identity.api.dependencies import require_admin


class _FakeAuthService:
    def __init__(self, payload: dict[str, Any] | None) -> None:
        self._payload = payload

    def validate_token(self, token: str) -> dict[str, Any] | None:
        return self._payload


def _creds() -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials="token")


def test_require_admin_accepts_admin_payload() -> None:
    service = _FakeAuthService({"sub": "admin", "role": "admin"})
    payload = require_admin(credentials=_creds(), auth_service=service)
    assert payload["role"] == "admin"


def test_require_admin_rejects_non_admin_with_403() -> None:
    service = _FakeAuthService({"sub": "bob", "role": "member"})
    with pytest.raises(HTTPException) as exc:
        require_admin(credentials=_creds(), auth_service=service)
    assert exc.value.status_code == status.HTTP_403_FORBIDDEN


def test_require_admin_rejects_invalid_token_with_401() -> None:
    service = _FakeAuthService(None)
    with pytest.raises(HTTPException) as exc:
        require_admin(credentials=_creds(), auth_service=service)
    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED
