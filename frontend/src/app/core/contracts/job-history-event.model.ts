/** A tracked field's before/after values, or a bare changed flag for large
 *  fields (description) that are recorded as a flag only. */
export type ChangedValue = { old: string | null; new: string | null } | { changed: true };

export type JobHistoryEventType = 'inserted' | 'updated' | 'reopened' | 'closed';

export interface JobHistoryEvent {
  job_id: string;
  event: JobHistoryEventType;
  changed_fields: Record<string, ChangedValue>;
  reason: string | null;
  occurred_at: string;
  /** Read-side provenance; absent for closures from an unscoped sweep. */
  run_id?: string | null;
  run_trigger?: string | null;
  job_title?: string | null;
  job_company?: string | null;
  job_source?: string | null;
}
