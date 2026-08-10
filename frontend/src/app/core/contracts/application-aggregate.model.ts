import { JobSnapshot } from '@core/contracts/job-snapshot.model';
import { ApplicationMatch } from '@core/contracts/application-match.model';
import { CvOptimization } from '@core/contracts/cv-optimization.model';
import { ApplicationInterviewPrep } from '@core/contracts/application-interview-prep.model';
import { CoverLetter } from '@core/contracts/cover-letter.model';

export interface ApplicationAggregate {
  id: string;
  job_id: string | null;
  title: string;
  company: string;
  url: string | null;
  status: string;
  notes: string | null;
  location: string | null;
  remote_modality: 'remote' | 'hybrid' | 'on_site' | null;
  salary_range: string | null;
  source: string | null;
  posted_date: string | null;
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
