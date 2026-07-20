from pydantic_settings import BaseSettings


class MatchingSettings(BaseSettings):
    """Pre-ranking blend, semantic caches, and 10-dimension matching weights."""

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
    # Bounds for the in-process embedding caches (LRU eviction). Job vectors
    # are ~3 KB each; profile entries are one per distinct profile text.
    semantic_job_cache_size: int = 2000
    semantic_profile_cache_size: int = 8
    # Per-job description truncation (chars) inside each of the six LLM
    # dimension-scorer prompts (seniority, compensation, growth, culture,
    # application strength, interview readiness).
    match_dimension_job_char_limit: int = 4000

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
