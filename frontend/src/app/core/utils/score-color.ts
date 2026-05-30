import { classifyScoreTier } from './classify-score-tier';
import { SCORE_NULL_COLOR } from './score-null-color';
import { SCORE_TIER_COLOR_MAP } from './score-tier-color-map';

// Maps a 0-1 score (or null) to its tier hex color.
export function scoreColor(score: number | null): string {
  if (score === null) return SCORE_NULL_COLOR;
  return SCORE_TIER_COLOR_MAP[classifyScoreTier(score)];
}
