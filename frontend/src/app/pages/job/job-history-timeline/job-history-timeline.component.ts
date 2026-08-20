import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  OnInit,
  inject,
  input,
  signal,
} from '@angular/core';
import { DatePipe } from '@angular/common';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { IngestionService } from '../../../core/services/ingestion.service';
import {
  ChangedValue,
  JobHistoryEvent,
  JobHistoryEventType,
} from '@core/contracts/job-history-event.model';

const EVENT_LABELS: Record<JobHistoryEventType, string> = {
  inserted: 'Ingested',
  updated: 'Updated',
  reopened: 'Reopened',
  closed: 'Closed',
};

const REASON_LABELS: Record<string, string> = {
  probe_404: 'listing returned 404',
  closed_marker: 'page says the role is closed',
  dead_end_redirect: 'redirected to a generic page',
  expiry: 'listing expiry date passed',
  snapshot_disappearance: 'disappeared from the source feed',
};

// Human-readable labels for the tracked fields that can appear in
// `changed_fields`. Anything not listed here (there shouldn't be anything)
// falls back to the raw key.
const FIELD_LABELS: Record<string, string> = {
  title: 'Title',
  company: 'Company',
  salary_range: 'Salary',
  location: 'Location',
  employment_type: 'Employment type',
  description: 'Description',
};

@Component({
  selector: 'app-job-history-timeline',
  standalone: true,
  imports: [DatePipe],
  templateUrl: './job-history-timeline.component.html',
  styleUrl: './job-history-timeline.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class JobHistoryTimelineComponent implements OnInit {
  private readonly ingestion = inject(IngestionService);
  private readonly destroyRef = inject(DestroyRef);

  readonly jobId = input.required<string>();

  readonly events = signal<JobHistoryEvent[]>([]);
  readonly loading = signal(true);
  readonly error = signal<string | null>(null);

  ngOnInit(): void {
    this.load();
  }

  private load(): void {
    this.loading.set(true);
    this.error.set(null);
    this.ingestion
      .getJobHistory(this.jobId())
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: ({ events }) => {
          this.events.set(events);
          this.loading.set(false);
        },
        error: () => {
          this.error.set('Failed to load job history.');
          this.loading.set(false);
        },
      });
  }

  label(event: JobHistoryEvent): string {
    return EVENT_LABELS[event.event];
  }

  reasonLabel(reason: string | null): string | null {
    if (!reason) return null;
    return REASON_LABELS[reason] ?? reason;
  }

  changes(event: JobHistoryEvent): string[] {
    return Object.entries(event.changed_fields).map(([field, value]) =>
      this.describeChange(field, value),
    );
  }

  private describeChange(field: string, value: ChangedValue): string {
    const label = FIELD_LABELS[field] ?? field;
    if ('changed' in value) {
      return `${label} updated`;
    }
    return `${label}: was ${value.old || 'blank'}, now ${value.new || 'blank'}`;
  }
}
