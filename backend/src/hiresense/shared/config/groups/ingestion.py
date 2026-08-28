from pydantic import Field
from pydantic_settings import BaseSettings


class IngestionSettings(BaseSettings):
    """Ingestion scheduling, source enablement, filtering, and job closure/revalidation."""

    # Ingestion
    ingestion_schedule: str = "0 */6 * * *"
    enabled_job_sources: list[str] = [
        "remotive",
        "jobicy",
        "himalayas",
        "hn_hiring",
        "weworkremotely",
        "getonboard",
        "linkedin",
        "arbeitnow",
        "themuse",
        "dice",
        "yc_jobs",
        "ziprecruiter",
    ]
    # NOTE: `linkedin` is a fragile guest-endpoint HTML scraper (ToS-risky,
    # breaks on markup changes and rate-limits aggressively). It's kept enabled
    # by default for its on-site coverage; drop it here if it misbehaves.
    # `dice` uses Dice's official MCP search. `yc_jobs` parses public Work at a
    # Startup Inertia JSON. `crunchboard` is off by default — its jobs.rss now
    # 301-redirects to jobboard.io and yields zero jobs.
    # Import fallbacks (`indeed`, `wellfound`, `glassdoor`, `monster`) are
    # opt-in — add them here and place JSONL/CSV under csv_import_dir.

    # Directory CSV-import file_path filters are confined to (path-traversal guard).
    csv_import_dir: str = "./csv_imports"

    # Ingestion job-listing default minimum match score (0.0–1.0). Jobs with
    # match_score below this value are hidden from the listing. Override per
    # request with the ?min_score= query param. Keep persistence independent:
    # match scores are profile-dependent and must not be used to delete jobs.
    ingestion_min_match_score: float = Field(default=0.4, ge=0.0, le=1.0)

    # Hard cap on the ?page_size accepted by job-listing endpoints. Values
    # above this are clamped server-side to bound per-request memory and
    # scoring cost.
    ingestion_max_page_size: int = 100

    # Cold-start fairness for the all-sources match ranking: on a full rescore,
    # LLM quick-score the top-N heuristic jobs of EVERY source (in addition to
    # the visible page) so a strong job from a source the heuristic underrates
    # (e.g. getonboard's structured tags) can reach page 1 without the user
    # first filtering by that source. Champions are cached per profile, so the
    # steady-state extra LLM cost is zero. 0 disables the pass.
    ingestion_source_champions_per_source: int = 3

    # Cold-start ranking DEPTH (distinct from the per-source fairness above). The
    # page-level LLM pass only scores the visible 20, but page 1 is *selected*
    # before any real score exists — so a job the heuristic ranks 40th never
    # reaches a page, never gets scored, and never rises no matter how good it
    # is. On a full match-sorted rescore, LLM quick-score the global heuristic
    # top-N so the first page reflects real scores instead of converging over
    # several requests. Cached per profile, so steady-state cost is zero.
    # 0 disables the pass.
    ingestion_match_scoring_window: int = 100

    # Hide job listings whose posted_date is older than this many days (stale /
    # re-surfaced postings — e.g. WeWorkRemotely keeps the original RSS pubDate
    # while the site shows a bumped date). Jobs with no posted_date are never
    # hidden (unknown age). Override per request with ?max_age_days=. Default 0
    # disables the filter; the shipped .env sets 365 (hide > 1 year old).
    ingestion_max_job_age_days: int = 0

    # Ingestion cooldown (seconds between manual triggers)
    ingestion_cooldown_seconds: int = 300

    # Days to retain ingested jobs before HARD-deleting (GC backstop) at the
    # start of each /ingestion/fetch and /ingestion/scan-portals call. 0
    # disables pruning; values are capped at 10 years to prevent accidental
    # unbounded retention. With explicit closure detection now the primary
    # lifecycle signal, this is just a floor to bound table growth — kept long
    # enough that closed jobs linger with their badge before deletion.
    ingestion_job_retention_days: int = Field(default=90, ge=0, le=3650)

    # Days to retain per-job history events before pruning, on the same pass
    # that prunes jobs. Independent of ingestion_job_retention_days: history is
    # small per row and is the only record of what a past run did, so it is
    # worth keeping at least as long as the jobs it describes. 0 disables
    # pruning entirely. The FK cascade is a second, independent bound —
    # deleting a job removes its history regardless of age.
    job_history_retention_days: int = Field(default=90, ge=0, le=3650)

    # --- Job closure / revalidation ---
    # Consecutive snapshot fetches a previously-seen job may be missing before
    # it is marked closed (guards against a transient/empty fetch).
    job_closure_miss_threshold: int = 2
    # Cadence consumed by the in-app scheduler for URL-probe revalidation when
    # SCHEDULER_ENABLED=true. When disabled, operators can still trigger
    # POST /ingestion/revalidate manually or from an external cron.
    job_revalidation_interval_hours: int = 24
    # Max jobs probed per sweep run (oldest-checked first) — bounds network cost.
    job_revalidation_batch: int = 100
    # Sources the URL-probe sweep skips entirely. hn_hiring/csv expose no
    # reliable per-URL closure signal; himalayas and jobicy answer every probe
    # with a challenge/403, so a probe can only ever return UNKNOWN — they burn
    # a request per job per sweep and close nothing. Those with a declared
    # expiry_date are closed by the sweep's expiry pass instead.
    job_revalidation_excluded_sources: list[str] = [
        "hn_hiring",
        "csv",
        "himalayas",
        "jobicy",
    ]
    # URL substrings that identify a redirect target as an expired-listing
    # landing page. A board that bounces a removed listing to a generic search
    # page (LinkedIn) is signalling closure in the redirect itself; recognising
    # it closes the job without fetching the landing page. See
    # domain/dead_end_redirect.py — a redirect to the site root is detected
    # structurally and needs no marker here.
    job_revalidation_expired_redirect_markers: list[str] = [
        "trk=expired_jd_redirect",
    ]
    # How many job sources fetch concurrently in one ingestion pass. Sources are
    # independent hosts, so their network waits overlap; the per-source DB and
    # indexing work downstream still runs serially, in declaration order.
    ingestion_source_concurrency: int = 8

    # Probe throttling. The politeness budget is per-host: `delay` is the
    # minimum seconds between two requests to the SAME board and
    # `host_concurrency` caps that board's in-flight probes, so unrelated boards
    # run in parallel instead of sharing one queue. `concurrency` is only a
    # whole-sweep ceiling on total in-flight requests.
    job_revalidation_concurrency: int = 12
    job_revalidation_host_concurrency: int = 4
    job_revalidation_delay: float = 0.5
    # SSRF hardening for the URL-probe sweep. probe_url derives from ingested,
    # attacker-influenceable data (job board / HN / CSV), so each probe target
    # (and every redirect hop) is validated to be http/https resolving to a
    # globally-routable address before the request; internal/loopback/link-local
    # (incl. 169.254.169.254 metadata) targets are refused → UNKNOWN (never
    # close a job on a blocked probe). The response body is streamed and read at
    # most this many bytes to bound memory against an adversarial huge page.
    job_revalidation_max_probe_bytes: int = 262144
    # Max redirect hops followed per probe; each hop is re-validated. 0 = don't
    # follow redirects at all.
    job_revalidation_max_redirects: int = 5
    # User-Agent sent on revalidation probes. The shared httpx client defaults to
    # `python-httpx/...`, which some listing hosts (e.g. weworkremotely) reject
    # with 403 — turning a live/closed signal into UNKNOWN. A realistic browser
    # UA gets those pages to respond. (Hosts with JS/fingerprint challenges, e.g.
    # himalayas, stay blocked regardless — those use expiry-based closure.)
    job_revalidation_user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    )
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
