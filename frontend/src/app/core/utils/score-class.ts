import { classifyScoreTier } from './classify-score-tier';
import { SCORE_TIER_CLASS_MAP } from './score-tier-class-map';

// Maps a 0-1 score to its tier CSS class name.
export function scoreClass(score: number): string {
  return SCORE_TIER_CLASS_MAP[classifyScoreTier(score)];
}
