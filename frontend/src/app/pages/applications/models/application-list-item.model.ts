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
}
