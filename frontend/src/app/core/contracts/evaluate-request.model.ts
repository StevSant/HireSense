export interface EvaluateRequest {
  job_id?: string;
  profile_id?: string;
  job_title?: string;
  company?: string;
  description?: string;
  skills?: string[];
  location?: string;
}
