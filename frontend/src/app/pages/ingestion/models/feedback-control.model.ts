import { FeedbackKind } from './feedback-kind.model';

// View-model for a single feedback button (kind + icon key + label).
export interface FeedbackControl {
  kind: FeedbackKind;
  /** Identifier for the inline SVG to render (e.g. 'thumb-up', 'ban'). */
  icon: string;
  label: string;
}
