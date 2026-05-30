import { ScoreTier } from './score-tier.model';

// Hex colors per score tier (green / amber / red), matching the dashboard palette.
export const SCORE_TIER_COLOR_MAP: Readonly<Record<ScoreTier, string>> = {
  high: '#16a34a',
  mid: '#ca8a04',
  low: '#dc2626',
};
