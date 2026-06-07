import { OutreachEventKind } from './outreach-event-kind.model';

export interface RecordRequest {
  application_id: string;
  kind: OutreachEventKind;
  message?: string;
  contact_name?: string;
  channel?: string;
}
