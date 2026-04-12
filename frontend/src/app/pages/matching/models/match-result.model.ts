import { ScoreBreakdown } from './score-breakdown.model';

export interface MatchResult {
  id: string;
  job_id: string;
  cv_id: string;
  overall_score: number;
  breakdown: ScoreBreakdown;
  matched_skills: string[];
  missing_skills: string[];
  pros: string[];
  cons: string[];
  recommendations: string[];
}
