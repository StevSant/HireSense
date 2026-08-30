export type SubmissionStatus =
  'queued' | 'claimed' | 'in_progress' | 'escalated' | 'submitted' | 'failed' | 'abandoned';

export interface SubmissionAttempt {
  id: string;
  application_id: string;
  job_id: string;
  packet_id: string | null;
  channel: string;
  target_url: string;
  status: SubmissionStatus;
  attempt_no: number;
  escalation_reason: string | null;
  escalated_fields: string[];
  evidence: Record<string, unknown>;
  created_at: string | null;
  finished_at: string | null;
}

export type SubmissionEventKind =
  'navigate' | 'fill' | 'click' | 'upload' | 'llm_decision' | 'escalate' | 'submit' | 'error';

export interface SubmissionEvent {
  id: string;
  attempt_id: string;
  seq: number;
  kind: SubmissionEventKind;
  payload: Record<string, unknown>;
  created_at: string | null;
}
