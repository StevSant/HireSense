export type InboxSignalState = 'pending' | 'applied' | 'dismissed';

export interface InboxSignal {
  id: string;
  message_id: string;
  from_address: string;
  subject: string;
  received_at: string;
  kind: string;
  company: string | null;
  role: string | null;
  confidence: number;
  matched_application_id: string | null;
  proposed_status: string | null;
  state: InboxSignalState;
  created_at: string | null;
}
