from pydantic_settings import BaseSettings


class AnalyticsSettings(BaseSettings):
    """Analytics dashboard aggregation caps + admin LLM-usage listing default."""

    # --- Analytics dashboard (read-only corpus/funnel aggregation) ---
    # TTL (seconds) for the heavy on-read results (salary distribution, target band).
    analytics_cache_ttl_seconds: int = 300
    # Target-salary band: how many profile-similar jobs to consider, and the
    # minimum parseable-salaried matches required before reporting a band.
    analytics_target_salary_top_k: int = 50
    analytics_target_salary_min_sample: int = 5
    # Search-focus "fresh fit": a profile-matched job counts as fresh if its
    # posted_date is within this many days.
    analytics_focus_fresh_days: int = 14
    # Sampling cap for the full-corpus aggregation scans (top-skills, skill-gap,
    # posting trend, salary distribution). These read every open posting into
    # memory; this caps the number of rows fetched per scan so memory/CPU stay
    # bounded as the corpus grows. It is a SAMPLE, not the whole corpus — the
    # resulting aggregates (skill %s, salary distribution, trend) are computed
    # over up to this many open postings. Raise if you want more exact figures
    # at the cost of memory; the corpus would need to exceed this before the
    # numbers are affected at all.
    analytics_corpus_sample_cap: int = 5000

    # --- Salary period normalization ---
    # Raw magnitude (pre-multiplier, currency-agnostic) below which an UNLABELED
    # salary figure is treated as monthly (×12) rather than annual. LATAM job
    # boards often list monthly pay with no period keyword; a bare "USD 2,500"
    # is monthly, not a 2,500/yr annual salary. Chosen below any realistic annual
    # salary so plausible annual figures are never downgraded. Only ever raises a
    # too-low unlabeled figure to monthly; labeled figures are unaffected.
    salary_annual_floor: int = 12000

    # --- Admin LLM usage dashboard ---
    # Default cap on rows returned by the "recent calls" listing (newest-first)
    # when the API/aggregator caller does not specify one. Bounds the unbounded
    # SELECT over the usage log. The /usage/calls endpoint clamps the per-request
    # ?limit= separately (1..500); this is the server-side default applied when
    # no explicit limit is passed.
    admin_usage_recent_limit: int = 100
