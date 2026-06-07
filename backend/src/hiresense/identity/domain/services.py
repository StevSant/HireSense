from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt


class AuthService:
    def __init__(self, username: str, password: str, jwt_secret: str, role: str = "admin") -> None:
        self._username = username
        self._password = password
        self._jwt_secret = jwt_secret
        self._role = role

    def login(self, username: str, password: str) -> str | None:
        if username == self._username and password == self._password:
            return self._create_token(username)
        return None

    def validate_token(self, token: str) -> dict[str, Any] | None:
        try:
            return jwt.decode(token, self._jwt_secret, algorithms=["HS256"])
        except JWTError:
            return None

    def _create_token(self, subject: str) -> str:
        expire = datetime.now(timezone.utc) + timedelta(hours=24)
        return jwt.encode(
            {"sub": subject, "role": self._role, "exp": expire},
            self._jwt_secret,
            algorithm="HS256",
        )
