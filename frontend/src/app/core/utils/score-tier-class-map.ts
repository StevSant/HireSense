import { ScoreTier } from './score-tier.model';

// CSS class names per score tier. These classes are defined in
// ingestion.component.scss (.score-high / .score-mid / .score-low).
export const SCORE_TIER_CLASS_MAP: Readonly<Record<ScoreTier, string>> = {
  high: 'score-high',
  mid: 'score-mid',
  low: 'score-low',
};
