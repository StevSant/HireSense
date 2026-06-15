import { ApplyProfile } from './apply-profile.model';
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
  linkedin_url: string | null;
  github_url: string | null;
  portfolio_url: string | null;
  apply_profile?: ApplyProfile | null;
  machine_translated?: boolean;
}
