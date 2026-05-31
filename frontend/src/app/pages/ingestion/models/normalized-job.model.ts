import { JobVerdict } from './job-verdict.model';

export interface NormalizedJob {
  id: string;
  title: string;
  company: string;
  description: string;
  skills: string[];
  location: string;
  salary_range: string | null;
  source: string;
  source_type: string;
  platform: string | null;
  categories: string[];
  department: string | null;
  url: string;
  posted_date: string | null;
  // Displayed match %. Mirrors llm_score when the LLM quick scorer has run,
  // else the heuristic skill+semantic blend.
  match_score: number | null;
  // Tier-1 quick LLM scoring (present once the visible page has been scored).
  llm_score: number | null;
  verdict: JobVerdict | null;
  reasons: string[];
  dealbreakers: string[];
  status?: 'open' | 'closed';
}
