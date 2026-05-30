import { SCORE_THRESHOLDS } from './score-thresholds';
import { ScoreTier } from './score-tier.model';

// Classifies a 0-1 score into its qualitative tier. This is the only place
// the threshold boundaries are compared — all color/class mapping goes through it.
export function classifyScoreTier(score: number): ScoreTier {
  if (score >= SCORE_THRESHOLDS.high) return 'high';
  if (score >= SCORE_THRESHOLDS.mid) return 'mid';
  return 'low';
}
