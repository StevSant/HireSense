import pytest


def test_settings_loads_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.setenv("AUTH_USERNAME", "admin")
    monkeypatch.setenv("AUTH_PASSWORD", "pass")
    monkeypatch.setenv("JWT_SECRET_KEY", "secret")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")

    from hiresense.config import Settings

    settings = Settings()
    assert settings.app_name == "HireSense"
    assert settings.app_port == 8000
    assert settings.llm_provider == "anthropic"
    assert settings.embedding_model == "all-mpnet-base-v2"
    assert settings.embedding_device == "cpu"
    assert settings.vector_store_provider == "pgvector"
    assert settings.weight_semantic == 15
    assert settings.weight_skill_match == 20


def test_settings_enabled_sources_parsed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.setenv("AUTH_USERNAME", "admin")
    monkeypatch.setenv("AUTH_PASSWORD", "pass")
    monkeypatch.setenv("JWT_SECRET_KEY", "secret")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    monkeypatch.setenv("ENABLED_JOB_SOURCES", "remotive,remoteok")

    from hiresense.config import Settings

    settings = Settings()
    assert settings.enabled_job_sources == ["remotive", "remoteok"]


@pytest.mark.parametrize(
    ("env_var", "placeholder"),
    [
        ("AUTH_PASSWORD", "changeme"),
        ("JWT_SECRET_KEY", "change-this-to-a-random-secret"),
    ],
)
def test_settings_rejects_placeholder_secrets(
    monkeypatch: pytest.MonkeyPatch, env_var: str, placeholder: str
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.setenv("AUTH_USERNAME", "admin")
    monkeypatch.setenv("AUTH_PASSWORD", "pass")
    monkeypatch.setenv("JWT_SECRET_KEY", "secret")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    monkeypatch.setenv(env_var, placeholder)

    from hiresense.config import Settings

    with pytest.raises(ValueError, match="placeholder"):
        Settings()


def test_settings_rejects_wildcard_cors_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.setenv("AUTH_USERNAME", "admin")
    monkeypatch.setenv("AUTH_PASSWORD", "pass")
    monkeypatch.setenv("JWT_SECRET_KEY", "secret")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    monkeypatch.setenv("CORS_ORIGINS", "*")

    from hiresense.config import Settings

    with pytest.raises(ValueError, match="wildcard"):
        Settings()


def test_otel_exporter_insecure_defaults_secure() -> None:
    # Reading the field default directly (not an instance) avoids backend/.env,
    # which opts into insecure=true for the local LGTM stack. The insecure OTLP
    # connection must be opt-in, so the code default is secure.
    from hiresense.config.groups import ObservabilitySettings

    assert ObservabilitySettings.model_fields["otel_exporter_insecure"].default is False


def test_cli_main_binds_configured_app_port(monkeypatch: pytest.MonkeyPatch) -> None:
    import uvicorn

    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.setenv("AUTH_USERNAME", "admin")
    monkeypatch.setenv("AUTH_PASSWORD", "pass")
    monkeypatch.setenv("JWT_SECRET_KEY", "secret")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    monkeypatch.setenv("APP_PORT", "9123")

    captured: dict[str, object] = {}
    monkeypatch.setattr(uvicorn, "run", lambda *args, **kwargs: captured.update(kwargs))

    from hiresense._cli import main

    main()

    assert captured["port"] == 9123


def test_embedding_device_configurable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.setenv("AUTH_USERNAME", "admin")
    monkeypatch.setenv("AUTH_PASSWORD", "pass")
    monkeypatch.setenv("JWT_SECRET_KEY", "secret")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    monkeypatch.setenv("EMBEDDING_DEVICE", "cuda")

    from hiresense.config import Settings

    settings = Settings()
    assert settings.embedding_device == "cuda"


def test_portfolio_settings_defaults_and_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.setenv("AUTH_USERNAME", "admin")
    monkeypatch.setenv("AUTH_PASSWORD", "pass")
    monkeypatch.setenv("JWT_SECRET_KEY", "secret")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    monkeypatch.setenv("PORTFOLIO_SOURCES", "supabase,github")
    # Pin these explicitly: the local backend/.env may populate them, and env
    # vars take precedence over the dotenv source.
    monkeypatch.setenv("PORTFOLIO_SUPABASE_URL", "")
    monkeypatch.setenv("PORTFOLIO_SUPABASE_ANON_KEY", "")

    from hiresense.config import Settings

    settings = Settings()
    assert settings.portfolio_sources == ["supabase", "github"]
    assert settings.portfolio_supabase_url == ""
    assert settings.portfolio_profile_char_cap == 1200


def test_portfolio_github_settings_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.setenv("AUTH_USERNAME", "admin")
    monkeypatch.setenv("AUTH_PASSWORD", "pass")
    monkeypatch.setenv("JWT_SECRET_KEY", "secret")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    # Pin against whatever the local backend/.env contains (env > dotenv).
    monkeypatch.setenv("PORTFOLIO_GITHUB_USERNAME", "")
    monkeypatch.setenv("PORTFOLIO_GITHUB_TOKEN", "")

    from hiresense.config import Settings

    settings = Settings()
    assert settings.portfolio_github_username == ""
    assert settings.portfolio_github_token == ""
    assert settings.portfolio_github_api_url == "https://api.github.com"
    assert settings.portfolio_github_max_repos == 30


def test_portfolio_citation_settings_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.setenv("AUTH_USERNAME", "admin")
    monkeypatch.setenv("AUTH_PASSWORD", "pass")
    monkeypatch.setenv("JWT_SECRET_KEY", "secret")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    monkeypatch.setenv("PORTFOLIO_PUBLIC_URL", "")

    from hiresense.config import Settings

    settings = Settings()
    assert settings.portfolio_public_url == ""
    assert settings.portfolio_ref_prefix == "hiresense"
    assert settings.portfolio_relevant_projects_top_n == 2


def test_portfolio_analytics_read_key_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.setenv("AUTH_USERNAME", "admin")
    monkeypatch.setenv("AUTH_PASSWORD", "pass")
    monkeypatch.setenv("JWT_SECRET_KEY", "secret")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    # Pin against local .env value so the test is not environment-sensitive.
    monkeypatch.setenv("PORTFOLIO_ANALYTICS_READ_KEY", "")

    from hiresense.config import Settings

    settings = Settings()
    assert settings.portfolio_analytics_read_key == ""
