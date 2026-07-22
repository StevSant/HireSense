export interface CreateApplicationRequest {
  job_id?: string;
  title?: string;
  company?: string;
  url?: string;
  notes?: string;
  location?: string;
  remote_modality?: 'remote' | 'hybrid' | 'on_site';
  salary_range?: string;
  source?: string;
  posted_date?: string;
}
