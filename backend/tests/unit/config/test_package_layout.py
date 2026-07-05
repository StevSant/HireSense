import pytest


def _set_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.setenv("AUTH_USERNAME", "admin")
    monkeypatch.setenv("AUTH_PASSWORD", "pass")
    monkeypatch.setenv("JWT_SECRET_KEY", "secret")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")


def test_public_symbols_importable(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required(monkeypatch)
    from hiresense.config import AppMode, Settings

    settings = Settings()
    # Flat access across several groups still works.
    assert settings.otel_enabled is True
    assert settings.database_url.startswith("postgresql")
    assert settings.weight_semantic == 15
    assert settings.portfolio_ref_prefix == "hiresense"
    assert settings.app_mode is AppMode.LOCAL


def test_groups_are_importable_from_package() -> None:
    from hiresense.config.groups import (
        CoreSettings,
        DatabaseSettings,
        LLMSettings,
        ObservabilitySettings,
        PortfolioSettings,
    )

    assert CoreSettings is not None
    assert DatabaseSettings is not None
    assert LLMSettings is not None
    assert ObservabilitySettings is not None
    assert PortfolioSettings is not None


def test_no_duplicate_field_across_groups() -> None:
    # Guards the mixin composition: two groups declaring the same field would
    # silently shadow. Assert the union has no collisions.
    from hiresense.config import groups as g

    seen: dict[str, str] = {}
    group_classes = [
        g.CoreSettings,
        g.ObservabilitySettings,
        g.DatabaseSettings,
        g.LLMSettings,
        g.HttpSettings,
        g.IngestionSettings,
        g.JobSourcesSettings,
        g.PortalsSettings,
        g.MatchingSettings,
        g.PreferenceSettings,
        g.AnalyticsSettings,
        g.SchedulingSettings,
        g.OutreachSettings,
        g.ApplicationsSettings,
        g.PortfolioSettings,
    ]
    for cls in group_classes:
        for field in cls.model_fields:
            assert field not in seen, f"{field} declared in both {seen[field]} and {cls.__name__}"
            seen[field] = cls.__name__
