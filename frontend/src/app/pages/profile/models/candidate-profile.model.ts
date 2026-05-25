import { CVSection } from './cv-section.model';

export interface CandidateProfile {
  id: string;
  name: string;
  email: string | null;
  phone: string | null;
  location: string | null;
  sections: CVSection[];
  raw_tex: string;
  language: string;
  skills: string[];
  name_override?: string | null;
  location_override?: string | null;
  linkedin_url?: string | null;
  github_url?: string | null;
  portfolio_url?: string | null;
}
