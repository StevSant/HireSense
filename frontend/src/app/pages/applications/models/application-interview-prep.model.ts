export interface ApplicationInterviewPrep {
  id: string;
  competencies_to_probe: string[];
  technical_topics: string[];
  negotiation_points: string[];
  matched_stories: { story_id: string; story_title: string; relevance: string }[];
  created_at: string | null;
}
