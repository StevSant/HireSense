from pydantic import Field
from pydantic_settings import BaseSettings


class IngestionSettings(BaseSettings):
    """Ingestion scheduling, source enablement, filtering, and job closure/revalidation."""

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
        "arbeitnow",
        "themuse",
    ]
    # NOTE: `linkedin` is a fragile guest-endpoint HTML scraper (ToS-risky,
    # breaks on markup changes and rate-limits aggressively). It's kept enabled
    # by default for its on-site coverage; drop it here if it misbehaves.

    # Directory CSV-import file_path filters are confined to (path-traversal guard).
    csv_import_dir: str = "./csv_imports"

    # Ingestion job-listing default minimum match score (0.0–1.0). Jobs with
    # match_score below this value are hidden from the listing. Override per
    # request with the ?min_score= query param. Default 0.0 (show all) — the
    # match column + sort=match_desc are the primary triage path. Bumping
    # this re-introduces the tag-dilution failure mode for verbose-tag
    # sources like getonboard; only raise if scoring is also fixed.
    ingestion_min_match_score: float = 0.0

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
    # Concurrent URL probes + per-request delay (seconds) for politeness.
    job_revalidation_concurrency: int = 2
    job_revalidation_delay: float = 1.0
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
