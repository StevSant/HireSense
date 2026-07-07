from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request, Response

# Fallbacks used when no Settings is wired on app.state (bare test apps). The
# real values come from CoreSettings; these mirror its defaults so a settings-less
# app still issues a coherent (local-style, non-Secure) cookie.
DEFAULT_SESSION_COOKIE_NAME = "hs_session"
DEFAULT_SESSION_COOKIE_SAMESITE = "strict"
DEFAULT_SESSION_MAX_AGE_SECONDS = 24 * 60 * 60


@dataclass(frozen=True)
class SessionCookieConfig:
    """Resolved attributes for the httpOnly session cookie."""

    name: str
    secure: bool
    samesite: str
    max_age_seconds: int


def resolve_session_cookie_config(request: Request) -> SessionCookieConfig:
    """Read cookie attributes from app.state.settings, falling back to defaults
    when settings is absent (bare test apps that only wire app.state.identity)."""
    settings = getattr(request.app.state, "settings", None)
    if settings is None:
        return SessionCookieConfig(
            name=DEFAULT_SESSION_COOKIE_NAME,
            secure=False,
            samesite=DEFAULT_SESSION_COOKIE_SAMESITE,
            max_age_seconds=DEFAULT_SESSION_MAX_AGE_SECONDS,
        )
    return SessionCookieConfig(
        name=settings.session_cookie_name,
        secure=bool(settings.session_cookie_secure),
        samesite=settings.session_cookie_samesite,
        max_age_seconds=settings.jwt_expiry_hours * 60 * 60,
    )


def set_session_cookie(response: Response, config: SessionCookieConfig, token: str) -> None:
    """Write the JWT into an httpOnly cookie scoped to the whole site."""
    response.set_cookie(
        key=config.name,
        value=token,
        max_age=config.max_age_seconds,
        httponly=True,
        secure=config.secure,
        samesite=config.samesite,
        path="/",
    )


def clear_session_cookie(response: Response, config: SessionCookieConfig) -> None:
    """Expire the session cookie server-side. Attributes must match the set call
    (path/secure/samesite) or some browsers keep the original cookie."""
    response.delete_cookie(
        key=config.name,
        httponly=True,
        secure=config.secure,
        samesite=config.samesite,
        path="/",
    )
