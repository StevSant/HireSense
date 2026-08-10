export interface AnalyzeRequest {
  job_id: string;
  cv_id: string;
  job_description: string;
  job_skills: string[];
  cv_summary: string;
  cv_skills: string[];
}
