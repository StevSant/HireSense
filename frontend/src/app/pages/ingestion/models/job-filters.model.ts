import { SeniorityLevel } from './seniority-level.model';

export interface JobFilters {
  source?: string;
  keyword?: string;
  location?: string;
  skills?: string;
  date_from?: string;
  date_to?: string;
  user_location?: string;
  strict_location?: boolean;
  sort?: 'match_desc' | 'date_desc';
  seniority?: SeniorityLevel[];
  max_years_experience?: number;
}
