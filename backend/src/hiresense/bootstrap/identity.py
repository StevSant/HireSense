from __future__ import annotations

from hiresense.config import Settings
from hiresense.identity.api.provider import IdentityProvider


def build_identity(settings: Settings) -> IdentityProvider:
    return IdentityProvider(
        username=settings.auth_username,
        password=settings.auth_password,
        jwt_secret=settings.jwt_secret_key,
        role=settings.auth_role,
        password_hash=settings.auth_password_hash,
        expiry_hours=settings.jwt_expiry_hours,
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
    )
