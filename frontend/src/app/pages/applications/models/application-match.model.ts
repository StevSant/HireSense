export interface ApplicationMatch {
  id: string;
  overall_score: number;
  semantic_score: number;
  skill_score: number;
  experience_score: number;
  language_score: number;
  matched_skills: string[];
  missing_skills: string[];
  pros: string[];
  cons: string[];
  recommendations: string[];
  cv_language: string;
  created_at: string | null;
}
