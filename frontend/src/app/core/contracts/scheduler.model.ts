export interface JobRun {
  job_name: string;
  started_at: string;
  finished_at: string;
  status: 'success' | 'failure' | 'skipped';
  detail: string | null;
  items_affected: number | null;
  duration_seconds: number | null;
}

export interface ScheduledJob {
  name: string;
  cron: string;
  enabled: boolean;
  last_run: JobRun | null;
  next_run_at: string | null;
}
