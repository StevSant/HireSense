from typing import Any

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from hiresense.config.groups import (
    AnalyticsSettings,
    ApplicationsSettings,
    CoreSettings,
    DatabaseSettings,
    HttpSettings,
    IngestionSettings,
    JobSourcesSettings,
    LLMSettings,
    MatchingSettings,
    ObservabilitySettings,
    OutreachSettings,
    PortalsSettings,
    PortfolioSettings,
    PreferenceSettings,
    ResearchSettings,
    SchedulingSettings,
)
from hiresense.config.mode import apply_mode
from hiresense.config.sources import (
    _CommaSeparatedDotEnvSource,
    _CommaSeparatedEnvSource,
)


class Settings(
    CoreSettings,
    ObservabilitySettings,
    DatabaseSettings,
    LLMSettings,
    HttpSettings,
    IngestionSettings,
    JobSourcesSettings,
    PortalsSettings,
    MatchingSettings,
    PreferenceSettings,
    AnalyticsSettings,
    SchedulingSettings,
    OutreachSettings,
    ApplicationsSettings,
    PortfolioSettings,
    ResearchSettings,
):
    """Composed application settings — flat attribute access over all groups."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @model_validator(mode="after")
    def _resolve_mode(self) -> "Settings":
        return apply_mode(self)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: Any,
        env_settings: Any,
        dotenv_settings: Any,
        file_secret_settings: Any,
    ) -> tuple[Any, ...]:
        return (
            init_settings,
            _CommaSeparatedEnvSource(settings_cls),
            _CommaSeparatedDotEnvSource(settings_cls),
            file_secret_settings,
        )
