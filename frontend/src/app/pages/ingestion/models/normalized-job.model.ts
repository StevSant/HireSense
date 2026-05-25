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
  match_score: number | null;
}
