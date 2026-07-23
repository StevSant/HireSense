import { ScreeningAnswer } from './screening-answer.model';

// One-per-person answer bank for application forms (Apply Assist). Mirrors the
// backend ApplyProfile; sent to PUT /profile/apply-profile.
export interface ApplyProfile {
  preferred_name: string | null;
  work_authorization: string | null;
  // Optional while clients may still receive profiles saved before this field
  // was introduced; the editor falls back to the legacy boolean in that case.
  work_authorization_status?: 'authorized' | 'requires_sponsorship' | 'unknown';
  requires_visa_sponsorship: boolean | null;
  desired_salary: string | null;
  years_of_experience: number | null;
  willing_to_relocate: boolean | null;
  start_availability: string | null;
  screening_answers: ScreeningAnswer[];
}
