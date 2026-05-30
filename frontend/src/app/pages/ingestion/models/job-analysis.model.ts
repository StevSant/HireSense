import { AnalysisDimension } from './analysis-dimension.model';

// Tier-2 deep match analysis returned by GET /ingestion/jobs/:id/analysis.
export interface JobAnalysis {
  job_id: string;
  overall_score: number;
  verdict: string;
  dimensions: AnalysisDimension[];
  matched_skills: string[];
  missing_skills: string[];
  pros: string[];
  cons: string[];
  recommendations: string[];
  narrative: string;
}
