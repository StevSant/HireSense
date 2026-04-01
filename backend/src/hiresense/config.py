from typing import Any, ClassVar

from pydantic import model_validator
from pydantic_settings import BaseSettings, EnvSettingsSource, SettingsConfigDict


class _CommaSeparatedEnvSource(EnvSettingsSource):
    """Custom env source that handles comma-separated list fields gracefully."""

    _COMMA_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {"enabled_job_sources", "supported_languages"}
    )

    def prepare_field_value(
        self,
        field_name: str,
        field: Any,
        value: Any,
        value_is_complex: bool,
    ) -> Any:
        if field_name in self._COMMA_FIELDS and isinstance(value, str):
            return [s.strip() for s in value.split(",") if s.strip()]
        return super().prepare_field_value(field_name, field, value, value_is_complex)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Core
    app_name: str = "HireSense"
    app_port: int = 8000
    debug: bool = False

    # Auth
    auth_username: str
    auth_password: str
    jwt_secret_key: str

    # Database
    database_url: str

    # LLM
    llm_provider: str = "anthropic"
    llm_api_key: str
    llm_model: str = "claude-sonnet-4-6"
    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-3-small"
    embedding_api_key: str

    # Vector Store
    vector_store_provider: str = "pgvector"

    # HTTP
    http_timeout: float = 30.0

    # Ingestion
    ingestion_schedule: str = "0 */6 * * *"
    enabled_job_sources: list[str] = [
        "remotive",
        "remoteok",
        "jobicy",
        "himalayas",
        "hn_hiring",
        "weworkremotely",
        "getonboard",
    ]

    # LaTeX
    latex_compiler: str = "xelatex"
    cv_directory: str = "./cvs"

    # Language
    supported_languages: list[str] = ["en", "es"]
    default_language: str = "en"

    # Matching weights
    weight_semantic: int = 30
    weight_skill_match: int = 40
    weight_experience: int = 20
    weight_language: int = 10

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
            dotenv_settings,
            file_secret_settings,
        )
