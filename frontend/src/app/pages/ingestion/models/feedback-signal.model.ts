import { FeedbackKind } from './feedback-kind.model';

// Mirrors backend FeedbackSignalResponse.
export interface FeedbackSignal {
  id: string | null;
  job_id: string;
  kind: FeedbackKind;
  created_at: string | null;
}
