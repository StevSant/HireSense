export interface AutopilotDraft {
  id: string;
  job_id: string;
  application_id: string | null;
  job_title: string | null;
  company: string | null;
  status: 'drafted' | 'partial' | 'failed';
  detail: string | null;
}
