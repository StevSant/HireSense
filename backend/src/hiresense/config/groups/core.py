from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings

from hiresense.config.mode import AppMode

# Known sample values shipped in .env.example. Startup refuses to run with
# these so a copied-but-unedited .env fails loudly instead of exposing the
# instance behind guessable credentials.
_PLACEHOLDER_SECRETS: frozenset[str] = frozenset(
    {
        "changeme",
        "change-this-to-a-random-secret",
    }
)


class CoreSettings(BaseSettings):
    """Core application, CORS, auth, language, upload, batch, and rate-limit settings."""

    # Core
    # Runtime mode. local = degrade missing LLM/auth config (dev-friendly);
    # production = strict, refuses to boot without every required value.
    app_mode: AppMode = AppMode.LOCAL
    app_name: str = "HireSense"
    app_port: int = 8000
    debug: bool = False
    cors_origins: list[str] = ["http://localhost:4200"]
    # Explicit CORS method/header allow-lists. Wildcards are deliberately not
    # the default: combined with allow_credentials=True they over-grant to any
    # origin that slips into cors_origins.
    cors_allow_methods: list[str] = ["GET", "POST", "PUT", "PATCH", "DELETE"]
    cors_allow_headers: list[str] = ["Authorization", "Content-Type"]

    # Auth. Blank in local mode → degraded (ephemeral dev secret + default
    # creds, see config.mode.apply_mode); required in production.
    auth_username: str = ""
    auth_password: str = ""
    # Optional scrypt hash of the admin password (scrypt$n$r$p$salt$hash). When
    # set it takes precedence over AUTH_PASSWORD and the plaintext is never
    # retained by the auth service. Generate with:
    #   python -c "from hiresense.identity.domain import hash_password; print(hash_password('pw'))"
    auth_password_hash: str = ""
    jwt_secret_key: str = ""

    @field_validator("app_mode", mode="before")
    @classmethod
    def _normalize_app_mode(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("auth_password", "jwt_secret_key")
    @classmethod
    def _reject_placeholder_secrets(cls, value: str, info: Any) -> str:
        if value in _PLACEHOLDER_SECRETS:
            raise ValueError(
                f"{info.field_name} is still set to the .env.example placeholder; "
                'generate a real value (e.g. python -c "import secrets; print(secrets.token_urlsafe(48))")'
            )
        return value

    # Role embedded in issued tokens. A single-user instance is admin by default;
    # set to a non-admin value to genuinely exercise the admin gate.
    auth_role: str = "admin"

    # Session token lifetime (hours). Also drives the session cookie max-age so
    # the browser evicts the cookie in lock-step with token expiry.
    jwt_expiry_hours: int = 24

    # Session cookie (httpOnly) that carries the JWT for the SPA. The token is
    # never exposed to JavaScript (XSS can't exfiltrate it); the browser attaches
    # the cookie automatically on same-origin requests. The `Authorization:
    # Bearer` header is still accepted as a fallback for API tooling and tests.
    session_cookie_name: str = "hs_session"
    # Secure flag is mode-aware: None → resolved by APP_MODE (on in production,
    # off for local http dev) in config.mode.apply_mode. Set true/false to force.
    session_cookie_secure: bool | None = None
    # SameSite=strict is the CSRF mitigation for the cookie: the browser never
    # sends it on cross-site requests, so forged requests carry no session.
    session_cookie_samesite: str = "strict"

    # Language
    supported_languages: list[str] = ["en", "es"]
    default_language: str = "en"

    # Seconds the shutdown lifespan waits for in-flight domain-event handlers
    # before cancelling them.
    event_bus_drain_timeout_seconds: float = 5.0

    # --- Rate limiting (expensive endpoints) ---
    # In-process sliding-window limiter applied to LLM/network-heavy endpoints
    # (ingestion fetch/scan/list/analysis/backfill, matching, optimization).
    # Keyed by client IP. Disable for load tests with RATE_LIMIT_ENABLED=false.
    rate_limit_enabled: bool = True
    rate_limit_max_requests: int = 30
    rate_limit_window_seconds: float = 60.0

    # Upload
    max_upload_bytes: int = 10 * 1024 * 1024  # 10 MB

    # Batch processing
    batch_concurrency: int = 3

    # Pagination (list endpoints: applications, cover letters, tracking)
    # Default page size when the client omits ?limit — generous so existing
    # single-page consumers keep seeing their whole list; clients may request a
    # smaller page explicitly.
    default_page_size: int = 100
    # Hard cap on ?limit for those endpoints: a single request can never pull
    # more than this many rows, bounding response size and query cost.
    max_page_size: int = 500
