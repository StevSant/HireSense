import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  OnInit,
  inject,
  signal,
} from '@angular/core';
import { DatePipe } from '@angular/common';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { IngestionService } from '../../../core/services/ingestion.service';
import { IngestionRunSummary } from '@core/contracts/ingestion-run.model';
import { JobHistoryEvent, JobHistoryEventType } from '@core/contracts/job-history-event.model';

// Fallbacks below guard against the backend introducing a new trigger,
// status, or event value before a matching frontend release ships — the raw
// enum must never leak into the UI (a real finding on the job-history
// timeline this page borrows its pattern from).
const TRIGGER_LABELS: Record<string, string> = {
  fetch: 'Manual fetch',
  scheduler: 'Scheduled',
  portal_scan: 'Portal scan',
};
const UNKNOWN_TRIGGER_LABEL = 'Unknown trigger';

const STATUS_LABELS: Record<string, string> = {
  running: 'Running',
  completed: 'Completed',
  failed: 'Failed',
};
const UNKNOWN_STATUS_LABEL = 'Unknown status';

const EVENT_LABELS: Record<JobHistoryEventType, string> = {
  inserted: 'Inserted',
  updated: 'Updated',
  reopened: 'Reopened',
  closed: 'Closed',
};
const UNKNOWN_EVENT_LABEL = 'Event';

@Component({
  selector: 'app-runs',
  standalone: true,
  imports: [DatePipe],
  templateUrl: './runs.component.html',
  styleUrl: './runs.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class RunsComponent implements OnInit {
  private readonly ingestion = inject(IngestionService);
  private readonly destroyRef = inject(DestroyRef);

  readonly runs = signal<IngestionRunSummary[]>([]);
  readonly loading = signal(true);
  readonly error = signal<string | null>(null);

  readonly expandedRunId = signal<string | null>(null);
  readonly eventsByRunId = signal<Record<string, JobHistoryEvent[]>>({});
  readonly eventsLoading = signal<string | null>(null);
  // Scoped by run id, like eventsLoading — a stale error for one run must
  // never bleed into another run's already-cached (successfully loaded) row.
  readonly eventsErrorByRunId = signal<Record<string, string>>({});

  ngOnInit(): void {
    this.load();
  }

  private load(): void {
    this.loading.set(true);
    this.error.set(null);
    this.ingestion
      .listRuns()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: ({ runs }) => {
          this.runs.set(runs);
          this.loading.set(false);
        },
        error: () => {
          this.error.set('Failed to load ingestion runs.');
          this.loading.set(false);
        },
      });
  }

  toggleRun(runId: string): void {
    if (this.expandedRunId() === runId) {
      this.expandedRunId.set(null);
      return;
    }
    this.expandedRunId.set(runId);
    if (this.eventsByRunId()[runId]) return;

    this.eventsLoading.set(runId);
    this.eventsErrorByRunId.update((byId) => {
      const next = { ...byId };
      delete next[runId];
      return next;
    });
    this.ingestion
      .getRun(runId)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: ({ events }) => {
          this.eventsByRunId.update((byId) => ({ ...byId, [runId]: events }));
          this.eventsLoading.set(null);
        },
        error: () => {
          this.eventsErrorByRunId.update((byId) => ({
            ...byId,
            [runId]: 'Failed to load run events.',
          }));
          this.eventsLoading.set(null);
        },
      });
  }

  triggerLabel(trigger: string): string {
    return TRIGGER_LABELS[trigger] ?? UNKNOWN_TRIGGER_LABEL;
  }

  statusLabel(status: string): string {
    return STATUS_LABELS[status] ?? UNKNOWN_STATUS_LABEL;
  }

  eventLabel(event: JobHistoryEvent): string {
    return EVENT_LABELS[event.event] ?? UNKNOWN_EVENT_LABEL;
  }

  // Null while a run is still in flight — must render as "no duration", not
  // NaN/0s/negative.
  duration(run: IngestionRunSummary): string | null {
    if (!run.finished_at) return null;
    const startMs = new Date(run.started_at).getTime();
    const endMs = new Date(run.finished_at).getTime();
    const totalSeconds = Math.max(0, Math.round((endMs - startMs) / 1000));

    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;

    const parts: string[] = [];
    if (hours) parts.push(`${hours}h`);
    if (hours || minutes) parts.push(`${minutes}m`);
    parts.push(`${seconds}s`);
    return parts.join(' ');
  }
}
