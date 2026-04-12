import { CVSection } from './cv-section.model';

export interface CandidateProfile {
  id: string;
  name: string;
  email: string | null;
  phone: string | null;
  location: string | null;
  sections: CVSection[];
  language: string;
  skills: string[];
}
