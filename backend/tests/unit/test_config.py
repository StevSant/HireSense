import pytest


def test_settings_loads_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.setenv("AUTH_USERNAME", "admin")
    monkeypatch.setenv("AUTH_PASSWORD", "pass")
    monkeypatch.setenv("JWT_SECRET_KEY", "secret")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    monkeypatch.setenv("EMBEDDING_API_KEY", "sk-test")

    from hiresense.config import Settings

    settings = Settings()
    assert settings.app_name == "HireSense"
    assert settings.app_port == 8000
    assert settings.llm_provider == "anthropic"
    assert settings.vector_store_provider == "pgvector"
    assert settings.weight_semantic == 30
    assert settings.weight_skill_match == 40
    assert settings.weight_experience == 20
    assert settings.weight_language == 10


def test_settings_enabled_sources_parsed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.setenv("AUTH_USERNAME", "admin")
    monkeypatch.setenv("AUTH_PASSWORD", "pass")
    monkeypatch.setenv("JWT_SECRET_KEY", "secret")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    monkeypatch.setenv("EMBEDDING_API_KEY", "sk-test")
    monkeypatch.setenv("ENABLED_JOB_SOURCES", "remotive,remoteok")

    from hiresense.config import Settings

    settings = Settings()
    assert settings.enabled_job_sources == ["remotive", "remoteok"]
