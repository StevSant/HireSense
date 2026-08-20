import { JobHistoryEvent } from './job-history-event.model';

export interface IngestionRunSummary {
  id: string;
  started_at: string;
  finished_at: string | null;
  trigger: string;
  status: string;
  inserted: number;
  updated: number;
  reopened: number;
  closed: number;
}

export interface IngestionRunDetail {
  run: IngestionRunSummary;
  events: JobHistoryEvent[];
}
