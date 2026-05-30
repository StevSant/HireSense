from typing import Any, ClassVar

from pydantic_settings import BaseSettings, DotEnvSettingsSource, EnvSettingsSource, SettingsConfigDict


class _CommaSeparatedMixin:
    """Mixin that splits comma-separated strings into lists for known fields."""

    _COMMA_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {"enabled_job_sources", "supported_languages", "getonboard_categories"}
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
    # Fernet key for encrypting API keys at rest in the admin llm_settings
    # row. Generate via: Fernet.generate_key().decode(). Empty disables
    # encryption-backed persistence; the admin endpoints will refuse to
    # save a new key and the runtime falls back to llm_api_key from env.
    llm_settings_encryption_key: str = ""
    embedding_model: str = "all-mpnet-base-v2"
    embedding_device: str = "cpu"
    # Embedding vector dimension — must match the model above (all-mpnet-base-v2
    # produces 768-dim vectors). The pgvector column and ANN index are sized to
    # this; changing the model means changing this and re-running the embedding
    # migration/backfill.
    embedding_dim: int = 768

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
    # request with the ?min_score= query param. Default 0.0 (show all) — the
    # match column + sort=match_desc are the primary triage path. Bumping
    # this re-introduces the tag-dilution failure mode for verbose-tag
    # sources like getonboard; only raise if scoring is also fixed.
    ingestion_min_match_score: float = 0.0

    # Language
    supported_languages: list[str] = ["en", "es"]
    default_language: str = "en"

    # Ingestion cooldown (seconds between manual triggers)
    ingestion_cooldown_seconds: int = 300

    # Days to retain ingested jobs before pruning at the start of each
    # /ingestion/fetch and /ingestion/scan-portals call. 0 disables pruning.
    ingestion_job_retention_days: int = 30

    # Job source URLs
    jobicy_api_url: str = "https://jobicy.com/api/v2/remote-jobs"
    himalayas_api_url: str = "https://himalayas.app/jobs/api"
    hn_algolia_api_url: str = "https://hn.algolia.com/api/v1"
    weworkremotely_rss_url: str = "https://weworkremotely.com/remote-jobs.rss"
    getonboard_api_url: str = "https://www.getonbrd.com/api/v0"
    # Getonbrd category IDs to ingest. Empty list falls back to /search/jobs
    # (no category filter). Tech-leaning defaults; widen via env if you want
    # design / marketing / support roles too.
    getonboard_categories: list[str] = [
        "programming",
        "mobile-developer",
        "design-ux",
        "machine-learning-ai",
        "sysadmin-devops-qa",
        "data-science-analytics",
        "cybersecurity",
        "hardware-electronics",
    ]
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

    # Pre-ranking blend weights (2-signal: skill-overlap vs. semantic similarity).
    # These are dedicated floats for the global pre-ranker and reproduce the
    # current effective 0.4/0.6 behavior. Do NOT reuse weight_skill_match /
    # weight_semantic — those are int percentages for the 10-dim deep matcher
    # and normalize to ~0.571/0.429, the inverse of the intended blend.
    prerank_weight_skill: float = 0.4
    prerank_weight_semantic: float = 0.6
    # Maximum number of jobs passed to PgVectorStore.search() during pre-ranking.
    # A cap larger than the corpus keeps the global-ordering guarantee intact
    # while bounding ANN query cost on large data sets.
    prerank_top_k_cap: int = 2000

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

    # Match scoring (LLM model routing). The job list shows an LLM-gated quick
    # score (cheap model, batched per visible page); the detail panel can run a
    # deeper single-job analysis (advanced model). These are the out-of-the-box
    # default models per feature — the admin can override either in the LLM
    # Settings UI (feature keys: match_quick_scorer / match_deep_analyzer).
    match_quick_model: str = "claude-haiku-4-5"
    match_deep_model: str = "claude-sonnet-4-6"
    # Jobs scored per quick-scorer LLM call (the page is scored in one batched
    # request). Defaults to the listing page size.
    match_quick_batch_size: int = 20
    # Per-job description truncation (chars) inside the batched quick prompt.
    match_quick_job_char_limit: int = 1500
    # Per-job description truncation (chars) for the deeper single-job analysis.
    match_deep_job_char_limit: int = 6000

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
