// Mirrors backend PreferenceExplanation.
export interface PreferenceExplanation {
  active: boolean;
  total_signals: number;
  positive_count: number;
  negative_count: number;
  counts_by_kind: Record<string, number>;
  drift_magnitude: number;
}
