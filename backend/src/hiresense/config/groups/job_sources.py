from pydantic_settings import BaseSettings


class JobSourcesSettings(BaseSettings):
    """Per-board job-source API URLs, credentials, and category filters."""

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
    # Max concurrent /companies/{id} lookups during a Get on Board fetch. Company
    # names are resolved one round-trip per distinct id; a bounded semaphore runs
    # them in parallel instead of serially (hundreds of jobs → hundreds of serial
    # GETs otherwise). Kept modest to stay polite to the public API.
    getonboard_company_concurrency: int = 8
    linkedin_jobs_url: str = "https://www.linkedin.com/jobs-guest/jobs/api"
    # LinkedIn per-job detail fetch rate-limit knobs (guest endpoint is aggressive)
    linkedin_detail_concurrency: int = 1
    linkedin_detail_delay: float = 1.0
    # Arbeitnow free Job Board API (Europe + remote, no auth).
    arbeitnow_api_url: str = "https://www.arbeitnow.com/api/job-board-api"
    # The Muse public Jobs API (global). Categories narrow the broad board to
    # dev-relevant roles; api_key is optional (raises the rate limit).
    themuse_api_url: str = "https://www.themuse.com/api/public/jobs"
    themuse_categories: list[str] = [
        "Software Engineering",
        "Data Science",
        "Design and UX",
        "Product Management",
        "IT",
    ]
    themuse_api_key: str = ""
    # Adzuna aggregator API (global on-site/hybrid + salary). Requires a free
    # app_id + app_key from developer.adzuna.com. Left out of the default
    # enabled_job_sources; only wired when both credentials are set. Countries
    # default LATAM-leaning (mx,br,ar); widen via env (gb,us,de,...).
    adzuna_api_url: str = "https://api.adzuna.com/v1/api/jobs"
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""
    adzuna_countries: list[str] = ["mx", "br", "ar"]
    adzuna_query: str = "software developer"

    # --- Expanded board sources (2026-07-24) ---
    # Dice official MCP search (no API key required for public search).
    dice_mcp_url: str = "https://mcp.dice.com/mcp"
    dice_query: str = "software engineer"
    dice_location: str = ""
    dice_remote_only: bool = False
    dice_page_limit: int = 3
    dice_jobs_per_page: int = 50
    dice_posted_date: str = ""  # ONE | THREE | SEVEN or blank
    dice_employment_types: list[str] = []

    # CrunchBoard official RSS (latest-window feed).
    crunchboard_rss_url: str = "https://www.crunchboard.com/jobs.rss"
    crunchboard_result_limit: int = 200

    # Y Combinator Work at a Startup (public Inertia JSON in HTML).
    yc_jobs_base_url: str = "https://www.workatastartup.com"
    yc_jobs_roles: list[str] = [
        "software-engineer",
        "product",
        "designer",
        "science",
    ]
    yc_jobs_remote_only: bool = False
    yc_jobs_enrich_companies: bool = True
    yc_jobs_company_enrich_limit: int = 25
    yc_jobs_result_limit: int = 200

    # Import-fallback sources (Indeed / Wellfound / Glassdoor / Monster).
    # Default filenames under csv_import_dir; override per fetch via filters.file_path.
    indeed_import_filename: str = "indeed_jobs.jsonl"
    wellfound_import_filename: str = "wellfound_jobs.jsonl"
    glassdoor_import_filename: str = "glassdoor_jobs.jsonl"
    monster_import_filename: str = "monster_jobs.jsonl"
