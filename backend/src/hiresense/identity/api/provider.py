from __future__ import annotations

from hiresense.identity.domain import AuthService


class IdentityProvider:
    def __init__(
        self,
        username: str,
        password: str,
        jwt_secret: str,
        role: str = "admin",
        password_hash: str = "",
        expiry_hours: int = 24,
        issuer: str = "hiresense",
        audience: str = "hiresense-api",
    ) -> None:
        self._auth_service = AuthService(
            username=username,
            password=password,
            jwt_secret=jwt_secret,
            role=role,
            password_hash=password_hash,
            expiry_hours=expiry_hours,
            issuer=issuer,
            audience=audience,
        )

    def get_auth_service(self) -> AuthService:
        return self._auth_service
