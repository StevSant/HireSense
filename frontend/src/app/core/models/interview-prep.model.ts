import { StoryMatch } from './story-match.model';

export interface InterviewPrep {
  job_title: string;
  company: string;
  matched_stories: StoryMatch[];
  competencies_to_probe: string[];
  technical_topics: string[];
  negotiation_points: string[];
}
