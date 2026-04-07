import { ApplicationStatus } from './application-status.model';

export interface TrackedApplication {
  id: string;
  job_id: string | null;
  title: string;
  company: string;
  url: string | null;
  status: ApplicationStatus;
  notes: string | null;
  applied_at: string | null;
  created_at: string;
  updated_at: string;
}
