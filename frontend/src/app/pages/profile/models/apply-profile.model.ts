import { ScreeningAnswer } from './screening-answer.model';

// One-per-person answer bank for application forms (Apply Assist). Mirrors the
// backend ApplyProfile; sent to PUT /profile/apply-profile.
export interface ApplyProfile {
  preferred_name: string | null;
  work_authorization: string | null;
  requires_visa_sponsorship: boolean | null;
  desired_salary: string | null;
  years_of_experience: number | null;
  willing_to_relocate: boolean | null;
  start_availability: string | null;
  screening_answers: ScreeningAnswer[];
}
