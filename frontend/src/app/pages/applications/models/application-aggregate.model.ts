import { JobSnapshot } from './job-snapshot.model';
import { ApplicationMatch } from './application-match.model';
import { CvOptimization } from './cv-optimization.model';
import { ApplicationInterviewPrep } from './application-interview-prep.model';
import { CoverLetter } from './cover-letter.model';

export interface ApplicationAggregate {
  id: string;
  job_id: string | null;
  title: string;
  company: string;
  url: string | null;
  status: string;
  notes: string | null;
  applied_at: string | null;
  created_at: string | null;
  updated_at: string | null;
  job_snapshot: JobSnapshot | null;
  latest_match: ApplicationMatch | null;
  latest_optimization: CvOptimization | null;
  latest_interview_prep: ApplicationInterviewPrep | null;
  latest_cover_letter: CoverLetter | null;
  match_count: number;
  optimization_count: number;
  interview_prep_count: number;
  cover_letter_count: number;
}
