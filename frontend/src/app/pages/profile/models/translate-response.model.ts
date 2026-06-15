import { CandidateProfile } from './candidate-profile.model';

export interface TranslateResponse {
  profile: CandidateProfile;
  pdf_ok: boolean;
  compile_error: string | null;
}
