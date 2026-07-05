import pytest


def _set_required(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set every field that is required in production to a real value."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.setenv("AUTH_USERNAME", "admin")
    monkeypatch.setenv("AUTH_PASSWORD", "pass")
    monkeypatch.setenv("JWT_SECRET_KEY", "secret")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")


def test_local_generates_ephemeral_jwt_when_blank(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_MODE", "local")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.setenv("AUTH_USERNAME", "")
    monkeypatch.setenv("AUTH_PASSWORD", "")
    monkeypatch.setenv("JWT_SECRET_KEY", "")
    monkeypatch.setenv("LLM_API_KEY", "")

    from hiresense.config import Settings

    settings = Settings()
    assert settings.jwt_secret_key  # non-empty, generated
    assert settings.auth_username == "admin"
    assert settings.auth_password  # generated dev password
    assert settings.llm_api_key == ""  # heuristic-only, not filled


def test_local_ephemeral_jwt_differs_across_builds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_MODE", "local")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.setenv("AUTH_USERNAME", "")
    monkeypatch.setenv("AUTH_PASSWORD", "")
    monkeypatch.setenv("JWT_SECRET_KEY", "")
    monkeypatch.setenv("LLM_API_KEY", "")

    from hiresense.config import Settings

    assert Settings().jwt_secret_key != Settings().jwt_secret_key


def test_local_missing_database_url_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_MODE", "local")
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("AUTH_USERNAME", "")
    monkeypatch.setenv("AUTH_PASSWORD", "")
    monkeypatch.setenv("JWT_SECRET_KEY", "")
    monkeypatch.setenv("LLM_API_KEY", "")

    from hiresense.config import Settings

    with pytest.raises(ValueError, match="DATABASE_URL"):
        Settings()


def test_production_missing_required_lists_all(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_MODE", "production")
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("AUTH_USERNAME", "")
    monkeypatch.setenv("AUTH_PASSWORD", "")
    monkeypatch.setenv("JWT_SECRET_KEY", "")
    monkeypatch.setenv("LLM_API_KEY", "")

    from hiresense.config import Settings

    with pytest.raises(ValueError) as exc:
        Settings()
    message = str(exc.value)
    for env in ("DATABASE_URL", "LLM_API_KEY", "AUTH_PASSWORD", "JWT_SECRET_KEY", "AUTH_USERNAME"):
        assert env in message


def test_env_override_wins_in_local(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_MODE", "local")
    _set_required(monkeypatch)
    monkeypatch.setenv("JWT_SECRET_KEY", "my-explicit-secret")

    from hiresense.config import Settings

    assert Settings().jwt_secret_key == "my-explicit-secret"


def test_production_with_all_required_boots(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_MODE", "production")
    _set_required(monkeypatch)

    from hiresense.config import Settings

    settings = Settings()
    assert settings.app_mode.value == "production"


def test_app_mode_defaults_to_local(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required(monkeypatch)
    monkeypatch.delenv("APP_MODE", raising=False)

    from hiresense.config import Settings

    assert Settings().app_mode.value == "local"
