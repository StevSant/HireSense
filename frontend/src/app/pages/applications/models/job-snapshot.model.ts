export interface JobSnapshot {
  id: string;
  description: string;
  required_skills: string[];
  source: 'ingested' | 'manual' | 'llm_extracted';
  updated_at: string | null;
}
