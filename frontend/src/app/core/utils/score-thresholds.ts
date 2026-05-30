// Match-score tier boundaries on the canonical 0-1 scale.
// A score >= high is a strong match; >= mid is moderate; below mid is weak.
// Single source of truth — every score color/class decision derives from these.

export const SCORE_THRESHOLDS = {
  high: 0.7,
  mid: 0.4,
} as const;
