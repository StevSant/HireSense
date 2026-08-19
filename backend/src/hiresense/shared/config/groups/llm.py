from pydantic_settings import BaseSettings


class LLMSettings(BaseSettings):
    """LLM provider/model, embeddings, and match-scoring model routing."""

    # LLM. Blank in local mode → heuristic-only matching (the tracked-LLM
    # factory returns None); required in production.
    llm_provider: str = "anthropic"
    llm_api_key: str = ""
    llm_model: str = "claude-sonnet-4-6"
    # Fernet key for encrypting API keys at rest in the admin llm_settings
    # row. Generate via: Fernet.generate_key().decode(). Empty disables
    # encryption-backed persistence; the admin endpoints will refuse to
    # save a new key and the runtime falls back to llm_api_key from env.
    llm_settings_encryption_key: str = ""
    # Gates Anthropic prompt caching (cache_control on the stable system-prompt
    # prefix). Only takes effect when the resolved feature config's provider is
    # "anthropic" — other providers are unaffected regardless of this flag.
    llm_prompt_cache_enabled: bool = True
    # Hard per-call timeout (seconds) for every LLM completion. Enforced with
    # asyncio.wait_for around the provider call, so a stalled connection can't
    # hang the cover-letter/optimize/match/interview endpoints indefinitely — on
    # expiry the call raises LLMTimeoutError, surfaced by the API as a 504.
    llm_timeout: float = 60.0
    embedding_model: str = "all-mpnet-base-v2"
    embedding_device: str = "cpu"
    # Texts per encode batch. Larger batches amortise the per-batch overhead of
    # CPU inference; 64 measured better than the library default of 32 without
    # a meaningful memory cost at this model size.
    embedding_batch_size: int = 64
    # Cap torch's intra-op threads. Unbounded, encode saturates every core and
    # starves the event loop, so concurrent source fetches stop making progress
    # while a batch runs. 0 leaves torch's own default in place.
    embedding_torch_threads: int = 4
    # Embedding vector dimension — must match the model above (all-mpnet-base-v2
    # produces 768-dim vectors). The pgvector column and ANN index are sized to
    # this; changing the model means changing this and re-running the embedding
    # migration/backfill.
    embedding_dim: int = 768

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
    # Max concurrent quick-scorer LLM chunk calls per request. Bounds fan-out
    # so a large rescore (many cache misses split into batch_size chunks)
    # can't fire one request per chunk all at once and trip the provider's
    # rate limit.
    match_quick_concurrency: int = 4
    # Per-job description truncation (chars) for the deeper single-job analysis.
    match_deep_job_char_limit: int = 6000
    # Default model for the combined 6-dimension scorer (feature key
    # match_dimension_scorer) — the one-call replacement for the 6 individual
    # dimension scorers. Admin-overridable in the LLM Settings UI like the
    # two models above.
    match_dimension_model: str = "claude-sonnet-4-6"

    # Default output token cap applied to any feature whose admin-configured
    # extra_params don't already set max_tokens. Prevents unbounded LLM output
    # (and its cost) on features nobody has explicitly tuned.
    llm_default_max_tokens: int = 2048
    # Smaller output cap for "classifier" features that return a short verdict
    # (a label, a confidence, a brief extraction) rather than long-form text.
    llm_classifier_max_tokens: int = 512
    # Larger output cap for features whose ONE response carries many items: the
    # quick scorer scores a whole page of jobs per call, the dimension scorer
    # returns six scored dimensions. Truncation there is not a shortened answer
    # but an unparseable one -- the JSON is cut mid-array and the whole batch is
    # discarded (see quick_scoring_service._parse), so the cap must cover the
    # widest batch, not the average one. A cap is a ceiling, not a charge: only
    # tokens actually emitted are billed.
    llm_batch_max_tokens: int = 6144
    # Cap on extracted CV/resume text (chars) passed to the LLM parser prompt.
    cv_parse_char_limit: int = 20000
