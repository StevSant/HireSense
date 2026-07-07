from __future__ import annotations

import logging
import secrets
import warnings
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hiresense.config.settings import Settings

_logger = logging.getLogger(__name__)


class AppMode(str, Enum):
    """Runtime mode. LOCAL degrades missing LLM/auth config; PRODUCTION is strict."""

    LOCAL = "local"
    PRODUCTION = "production"


# DATABASE_URL is required in BOTH modes (pgvector ANN needs Postgres; no SQLite
# fallback). LLM/auth are required in production but degrade in local.
_ALWAYS_REQUIRED: tuple[tuple[str, str], ...] = (("DATABASE_URL", "database_url"),)
_PRODUCTION_REQUIRED: tuple[tuple[str, str], ...] = (
    ("LLM_API_KEY", "llm_api_key"),
    ("AUTH_USERNAME", "auth_username"),
    ("AUTH_PASSWORD", "auth_password"),
    ("JWT_SECRET_KEY", "jwt_secret_key"),
)


def _missing(settings: "Settings", required: tuple[tuple[str, str], ...]) -> list[str]:
    return [env for env, attr in required if not getattr(settings, attr)]


def apply_mode(settings: "Settings") -> "Settings":
    """Resolve APP_MODE: raise an aggregated error for missing required config, or
    degrade blanks in local mode. Mutates and returns the settings instance."""
    # Session cookie Secure flag is mode-aware unless explicitly set: on in
    # production (HTTPS), off for local http dev where Secure would drop it.
    if settings.session_cookie_secure is None:
        settings.session_cookie_secure = settings.app_mode is AppMode.PRODUCTION

    if settings.app_mode is AppMode.PRODUCTION:
        missing = _missing(settings, _ALWAYS_REQUIRED + _PRODUCTION_REQUIRED)
        if missing:
            raise ValueError(
                "Production mode (APP_MODE=production) requires these settings, "
                "currently missing/blank:\n"
                + "\n".join(f"  - {name}" for name in missing)
                + "\nSet them in backend/.env or switch to APP_MODE=local for a "
                "degraded local run."
            )
        _logger.info("HireSense config resolved: APP_MODE=production")
        return settings

    # local mode
    missing_db = _missing(settings, _ALWAYS_REQUIRED)
    if missing_db:
        raise ValueError(
            "APP_MODE=local still requires these settings, currently missing/blank:\n"
            + "\n".join(f"  - {name}" for name in missing_db)
            + "\nStart Postgres (docker compose up db) and set DATABASE_URL — "
            "pgvector ANN has no SQLite fallback."
        )
    if not settings.llm_api_key:
        _logger.info(
            "APP_MODE=local: LLM_API_KEY not set — matching runs heuristic-only "
            "(no LLM scoring; LLM-backed features return a not-configured state)."
        )
    if not settings.jwt_secret_key:
        settings.jwt_secret_key = secrets.token_urlsafe(48)
        warnings.warn(
            "APP_MODE=local: JWT_SECRET_KEY not set — generated an EPHEMERAL secret; "
            "issued tokens reset on every restart. Set JWT_SECRET_KEY for stable "
            "sessions.",
            stacklevel=2,
        )
    if not settings.auth_username:
        settings.auth_username = "admin"
        _logger.warning("APP_MODE=local: AUTH_USERNAME not set — defaulting to 'admin'.")
    if not settings.auth_password:
        generated = secrets.token_urlsafe(16)
        settings.auth_password = generated
        warnings.warn(
            f"APP_MODE=local: AUTH_PASSWORD not set — generated a dev password: "
            f"{generated}  (set AUTH_PASSWORD to silence this).",
            stacklevel=2,
        )
    _logger.info("HireSense config resolved: APP_MODE=local")
    return settings
