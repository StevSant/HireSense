from typing import Any, ClassVar

from pydantic_settings import BaseSettings, DotEnvSettingsSource, EnvSettingsSource, SettingsConfigDict


class _CommaSeparatedMixin:
    """Mixin that splits comma-separated strings into lists for known fields."""

    _COMMA_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "enabled_job_sources",
            "supported_languages",
            "getonboard_categories",
            "job_closed_markers",
            "http_retry_status_codes",
        }
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

    # --- Observability (OpenTelemetry) ---
    # Master switch. When False, setup_telemetry() is a no-op and the app
    # boots with plain default logging.
    otel_enabled: bool = True
    # service.name resource attribute (shows up as the service in Grafana).
    otel_service_name: str = "hiresense-backend"
    # OTLP collector endpoint. EMPTY → console/terminal exporter fallback
    # (traces/metrics/logs print to stdout, no collector needed). Set to
    # http://otel-lgtm:4317 (compose) or http://localhost:4317 (host) to ship
    # to the LGTM stack.
    otel_exporter_otlp_endpoint: str = ""
    # deployment.environment resource attribute.
    deployment_environment: str = "development"
    # Root log level for the central dictConfig.
    log_level: str = "INFO"
    # "json" for structured logs (prod/LGTM) or "console" for human-readable
    # lines (local dev).
    log_format: str = "json"
    # Parent-based trace sampling ratio in [0.0, 1.0]. 1.0 = sample everything.
    otel_traces_sampler_ratio: float = 1.0
    # Use an insecure (plaintext, no-TLS) OTLP gRPC connection. True is correct
    # for the local LGTM stack / docker-compose; set False to use TLS.
    otel_exporter_insecure: bool = True

    # Auth
    auth_username: str
    auth_password: str
    jwt_secret_key: str
    # Role embedded in issued tokens. A single-user instance is admin by default;
    # set to a non-admin value to genuinely exercise the admin gate.
    auth_role: str = "admin"

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
    # Retry/backoff for the shared outbound HTTP client (wraps every ingestion
    # source adapter). Transient transport errors (timeout, connection reset)
    # and the status codes below are retried with exponential backoff
    # (delay = http_retry_base_delay * 2**attempt), up to http_max_retries
    # extra attempts. 0 retries disables retrying.
    http_max_retries: int = 3
    http_retry_base_delay: float = 0.5
    http_retry_status_codes: list[int] = [429, 500, 502, 503, 504]

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

    # Hide job listings whose posted_date is older than this many days (stale /
    # re-surfaced postings — e.g. WeWorkRemotely keeps the original RSS pubDate
    # while the site shows a bumped date). Jobs with no posted_date are never
    # hidden (unknown age). Override per request with ?max_age_days=. Default 0
    # disables the filter; the shipped .env sets 365 (hide > 1 year old).
    ingestion_max_job_age_days: int = 0

    # Language
    supported_languages: list[str] = ["en", "es"]
    default_language: str = "en"

    # Ingestion cooldown (seconds between manual triggers)
    ingestion_cooldown_seconds: int = 300

    # Days to retain ingested jobs before HARD-deleting (GC backstop) at the
    # start of each /ingestion/fetch and /ingestion/scan-portals call. 0
    # disables pruning. With explicit closure detection now the primary
    # lifecycle signal, this is just a floor to bound table growth — kept long
    # enough that closed jobs linger with their badge before deletion.
    ingestion_job_retention_days: int = 90

    # --- Job closure / revalidation ---
    # Consecutive snapshot fetches a previously-seen job may be missing before
    # it is marked closed (guards against a transient/empty fetch).
    job_closure_miss_threshold: int = 2
    # Advisory cadence for the URL-probe revalidation sweep. The app does NOT
    # self-schedule — POST /ingestion/revalidate is driven by an external cron;
    # this value documents the intended interval for that cron operator.
    job_revalidation_interval_hours: int = 24
    # Max jobs probed per sweep run (oldest-checked first) — bounds network cost.
    job_revalidation_batch: int = 100
    # Concurrent URL probes + per-request delay (seconds) for politeness.
    job_revalidation_concurrency: int = 2
    job_revalidation_delay: float = 1.0
    # Lowercased substring phrases that mark a 200-OK listing page as actually
    # closed (the listing stays live but says "no longer accepting", etc.).
    job_closed_markers: list[str] = [
        "no longer accepting applications",
        "position has been filled",
        "this job is closed",
        "this position is no longer available",
        "ya no está disponible",
        "esta oferta ya no está disponible",
    ]

    # Job source URLs
    remotive_api_url: str = "https://remotive.com/api/remote-jobs"
    remoteok_api_url: str = "https://remoteok.com/api"
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

    # --- Preference learning loop (taste vector via Rocchio relevance feedback) ---
    # Master switch: when False, query_vector() always returns the baseline.
    preference_enabled: bool = True
    # Blend coefficients: taste = normalize(alpha*baseline + beta*pos - gamma*neg)
    preference_alpha: float = 1.0
    preference_beta: float = 0.75
    preference_gamma: float = 0.5
    # Recency decay time constant in days (decay = exp(-age_days / tau)).
    preference_decay_tau_days: float = 90.0
    # Per-kind signal magnitudes (polarity is derived from the kind itself).
    preference_weight_thumbs_up: float = 1.0
    preference_weight_more_like_this: float = 1.0
    preference_weight_thumbs_down: float = 1.0
    preference_weight_not_interested: float = 1.5
    # Implicit (Phase 2) per-kind magnitudes — outcomes from the tracking pipeline.
    # Tiered: stronger ground-truth outcomes weigh more than a thumbs-up.
    preference_weight_applied: float = 1.0
    preference_weight_interviewing: float = 1.5
    preference_weight_offered: float = 2.5
    preference_weight_accepted: float = 3.0
    preference_weight_rejected: float = 1.5
    # Phase 2: layer an LLM-phrased natural-language drift summary over the
    # deterministic explanation. Falls back to summary=None on any LLM failure.
    preference_explanation_enabled: bool = True
    # Phase 2 dimension-weight nudging (preference -> matching composite).
    # Gate: minimum number of outcome-bearing signals before any nudge applies.
    # Below this, all overrides are zero and scoring is identical to today.
    preference_nudge_min_outcomes: int = 5
    # Hard clamp on the per-dimension integer weight delta (absolute bound).
    preference_nudge_clamp: int = 3
    # Scale factor mapping a dimension's [-1, 1] outcome correlation to an
    # integer delta before clamping (delta = round(correlation * scale)).
    preference_nudge_scale: float = 5.0

    # --- Analytics dashboard (read-only corpus/funnel aggregation) ---
    # TTL (seconds) for the heavy on-read results (salary distribution, target band).
    analytics_cache_ttl_seconds: int = 300
    # Target-salary band: how many profile-similar jobs to consider, and the
    # minimum parseable-salaried matches required before reporting a band.
    analytics_target_salary_top_k: int = 50
    analytics_target_salary_min_sample: int = 5
    # Sampling cap for the full-corpus aggregation scans (top-skills, skill-gap,
    # posting trend, salary distribution). These read every open posting into
    # memory; this caps the number of rows fetched per scan so memory/CPU stay
    # bounded as the corpus grows. It is a SAMPLE, not the whole corpus — the
    # resulting aggregates (skill %s, salary distribution, trend) are computed
    # over up to this many open postings. Raise if you want more exact figures
    # at the cost of memory; the corpus would need to exceed this before the
    # numbers are affected at all.
    analytics_corpus_sample_cap: int = 5000

    # --- Admin LLM usage dashboard ---
    # Default cap on rows returned by the "recent calls" listing (newest-first)
    # when the API/aggregator caller does not specify one. Bounds the unbounded
    # SELECT over the usage log. The /usage/calls endpoint clamps the per-request
    # ?limit= separately (1..500); this is the server-side default applied when
    # no explicit limit is passed.
    admin_usage_recent_limit: int = 100

    # --- Proactive Auto-Hunt (scheduled digest of new taste-ranked matches) ---
    # Top-N new matches per digest, and the minimum match score (0-1) to qualify.
    autohunt_top_n: int = 5
    autohunt_min_score: float = 0.6
    # First-run lookback window (no prior digest to anchor the watermark).
    autohunt_initial_lookback_days: int = 7
    # Digests older than this are pruned at the end of each run.
    autohunt_digest_retention_days: int = 90
    # Intended cron cadence — INFORMATIONAL ONLY; the app never self-schedules.
    autohunt_schedule: str = "0 9 * * *"

    # --- Outreach & Networking (on-brand message generation + follow-up nudges) ---
    # Path to the style-guide doc injected into the generation prompt (editable).
    outreach_style_guide_path: str = "docs/reference/message_To_apprach_recruiters.md"
    # Follow-up is "due" this many days after a 'sent' outreach with no progress.
    outreach_followup_cadence_days: int = 7
    # Soft length guard passed to the generator (chars).
    outreach_max_chars: int = 500
    # Intended cron cadence for the follow-up nudge sweep — INFORMATIONAL ONLY.
    outreach_followup_schedule: str = "0 10 * * *"

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
