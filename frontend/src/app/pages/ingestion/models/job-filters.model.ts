import { SeniorityLevel } from './seniority-level.model';

export interface JobFilters {
  source?: string;
  company?: string;
  keyword?: string;
  location?: string;
  skills?: string;
  date_from?: string;
  date_to?: string;
  user_location?: string;
  strict_location?: boolean;
  sort?:
    | 'match_asc' | 'match_desc'
    | 'posted_asc' | 'posted_desc'
    | 'title_asc' | 'title_desc'
    | 'company_asc' | 'company_desc'
    | 'location_asc' | 'location_desc'
    | 'source_asc' | 'source_desc'
    | 'date_desc'; // retained alias for backward compatibility
  seniority?: SeniorityLevel[];
  max_years_experience?: number;
}
