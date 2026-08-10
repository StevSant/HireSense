export interface ApplicationListItem {
  id: string;
  title: string;
  company: string;
  status: string;
  url: string | null;
  created_at: string | null;
  has_match: boolean;
  has_optimization: boolean;
  has_prep: boolean;
  latest_match_score: number | null;
  // Pipeline-view enrichment (folded in from the former Tracking page). Derived
  // from the linked ingested job when present, with persisted manual metadata
  // used as a field-by-field fallback.
  job_id: string | null;
  notes: string | null;
  applied_at: string | null;
  location: string | null;
  remote_modality: 'remote' | 'hybrid' | 'on_site' | null;
  salary_range: string | null;
  source: string | null;
  posted_date: string | null;
}
