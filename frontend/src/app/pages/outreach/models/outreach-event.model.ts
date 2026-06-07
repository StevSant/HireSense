import { OutreachEventKind } from './outreach-event-kind.model';

export interface OutreachEvent {
  id: string;
  application_id: string;
  kind: OutreachEventKind;
  contact_name: string | null;
  channel: string | null;
  message: string | null;
  created_at: string | null;
}
