import { ApplicationStatus } from '../../../core/models/application-status.model';

export interface UpdateApplicationRequest {
  status?: ApplicationStatus;
  title?: string;
  company?: string;
  url?: string | null;
  notes?: string | null;
  location?: string | null;
  remote_modality?: 'remote' | 'hybrid' | 'on_site' | null;
  salary_range?: string | null;
  source?: string | null;
  posted_date?: string | null;
}
