export interface NormalizedJob {
  id: string;
  title: string;
  company: string;
  description: string;
  skills: string[];
  location: string;
  salary_range: string | null;
  source: string;
  url: string;
  posted_date: string | null;
}
