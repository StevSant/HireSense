from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt

from hiresense.identity.domain.password_hasher import verify_password


class AuthService:
    def __init__(
        self,
        username: str,
        password: str,
        jwt_secret: str,
        role: str = "admin",
        password_hash: str = "",
    ) -> None:
        self._username = username
        # When a hash is configured (AUTH_PASSWORD_HASH), the plaintext is never
        # retained: verification runs against the hash only. The plaintext path
        # exists for the local-mode ephemeral dev password (config.mode), which
        # is generated at boot and has no hash.
        self._password_hash = password_hash
        self._password = "" if password_hash else password
        self._jwt_secret = jwt_secret
        self._role = role

    def login(self, username: str, password: str) -> str | None:
        if self._verify(username, password):
            return self._create_token(username)
        return None

    def _verify(self, username: str, password: str) -> bool:
        # A fully unconfigured credential must never authenticate (compare_digest
        # of two empty strings would otherwise return True).
        if not self._password_hash and not self._password:
            return False
        # compare_digest on both fields avoids leaking the username/password
        # length or match position through response timing. Compare UTF-8 bytes:
        # compare_digest raises TypeError on non-ASCII str, which would turn a
        # crafted non-ASCII credential into a 500 instead of a clean auth failure.
        username_ok = secrets.compare_digest(username.encode("utf-8"), self._username.encode("utf-8"))
        if self._password_hash:
            password_ok = verify_password(password, self._password_hash)
        else:
            password_ok = secrets.compare_digest(password.encode("utf-8"), self._password.encode("utf-8"))
        # Avoid short-circuiting so a wrong username and wrong password take the
        # same code path.
        return username_ok and password_ok

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
