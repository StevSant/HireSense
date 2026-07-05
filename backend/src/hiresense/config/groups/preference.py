from pydantic_settings import BaseSettings


class PreferenceSettings(BaseSettings):
    """Preference-learning loop (Rocchio taste vector + dimension-weight nudging)."""

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
