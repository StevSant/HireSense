import { JobVerdict } from './job-verdict.model';

export interface SourceProvenance {
  source: string;
  url?: string | null;
  posted_date?: string | null;
  job_id?: string;
  apply_url?: string | null;
}

export interface NormalizedJob {
  id: string;
  title: string;
  company: string;
  description: string;
  skills: string[];
  location: string;
  salary_range: string | null;
  employment_type?: string | null;
  equity_range?: string | null;
  source_metadata?: Record<string, unknown> | null;
  source: string;
  source_type: string;
  platform: string | null;
  categories: string[];
  department: string | null;
  url: string;
  // How the candidate applies, classified at ingestion. 'ats_form' means url is
  // a direct ATS application form (Greenhouse/Lever/Ashby/…) we can hand off to;
  // 'redirect' is an aggregator landing page; 'unknown' has no usable URL.
  application_method?: 'ats_form' | 'redirect' | 'unknown';
  // Detected ATS platform when application_method is 'ats_form', else null.
  ats_type?: string | null;
  // A URL we're confident is a direct application form (set for ats_form).
  apply_url?: string | null;
  posted_date: string | null;
  remote_modality?: 'remote' | 'hybrid' | 'on_site' | null;
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
