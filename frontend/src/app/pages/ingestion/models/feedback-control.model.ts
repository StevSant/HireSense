import { FeedbackKind } from './feedback-kind.model';

// View-model for a single feedback button (kind + display icon/label).
export interface FeedbackControl {
  kind: FeedbackKind;
  icon: string;
  label: string;
}
