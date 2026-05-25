from typing import Any, ClassVar

from pydantic import model_validator
from pydantic_settings import BaseSettings, DotEnvSettingsSource, EnvSettingsSource, SettingsConfigDict


class _CommaSeparatedMixin:
    """Mixin that splits comma-separated strings into lists for known fields."""

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


class _CommaSeparatedEnvSource(_CommaSeparatedMixin, EnvSettingsSource):
    pass


class _CommaSeparatedDotEnvSource(_CommaSeparatedMixin, DotEnvSettingsSource):
    pass


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Core
    app_name: str = "HireSense"
    app_port: int = 8000
    debug: bool = False
    cors_origins: list[str] = ["http://localhost:4200"]

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
    embedding_model: str = "all-mpnet-base-v2"
    embedding_device: str = "cpu"

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
        "linkedin",
    ]

    # LaTeX
    latex_compiler: str = "xelatex"
    latex_timeout_seconds: float = 60.0
    cv_directory: str = "./cvs"

    # Ingestion job-listing default minimum match score (0.0–1.0). Jobs with
    # match_score below this value are hidden from the listing. Override per
    # request with the ?min_score= query param (e.g. min_score=0 to show all).
    ingestion_min_match_score: float = 0.25

    # Language
    supported_languages: list[str] = ["en", "es"]
    default_language: str = "en"

    # Ingestion cooldown (seconds between manual triggers)
    ingestion_cooldown_seconds: int = 300

    # Job source URLs
    jobicy_api_url: str = "https://jobicy.com/api/v2/remote-jobs"
    himalayas_api_url: str = "https://himalayas.app/jobs/api"
    hn_algolia_api_url: str = "https://hn.algolia.com/api/v1"
    weworkremotely_rss_url: str = "https://weworkremotely.com/remote-jobs.rss"
    getonboard_api_url: str = "https://www.getonbrd.com/api/v0"
    linkedin_jobs_url: str = "https://www.linkedin.com/jobs-guest/jobs/api"
    # LinkedIn per-job detail fetch rate-limit knobs (guest endpoint is aggressive)
    linkedin_detail_concurrency: int = 1
    linkedin_detail_delay: float = 1.0

    # Portal scanning
    portals_config_path: str = "ingestion/config/portals.yml"
    portal_scan_timeout: float = 30.0
    greenhouse_api_url: str = "https://boards-api.greenhouse.io/v1/boards"
    lever_api_url: str = "https://api.lever.co/v0/postings"
    ashby_api_url: str = "https://api.ashbyhq.com/posting-api/job-board"

    # Matching weights (must sum to 100)
    weight_semantic: int = 15
    weight_skill_match: int = 20
    weight_experience: int = 10
    weight_language: int = 5
    weight_seniority: int = 10
    weight_compensation: int = 10
    weight_growth: int = 5
    weight_culture: int = 5
    weight_application: int = 10
    weight_interview: int = 10

    # Upload
    max_upload_bytes: int = 10 * 1024 * 1024  # 10 MB

    # Batch processing
    batch_concurrency: int = 3

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
