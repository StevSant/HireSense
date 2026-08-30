import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  OnInit,
  inject,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { SubmissionService } from '../../../core/services/submission.service';
import { SubmissionAttempt } from '@core/contracts/submission.model';

@Component({
  selector: 'app-submission-queue',
  standalone: true,
  imports: [FormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './queue.component.html',
  styleUrl: './queue.component.scss',
})
export class QueueComponent implements OnInit {
  private readonly service = inject(SubmissionService);
  private readonly destroyRef = inject(DestroyRef);

  readonly attempts = signal<SubmissionAttempt[]>([]);
  readonly loading = signal(false);
  readonly error = signal('');
  readonly notice = signal('');
  readonly expandedId = signal<string | null>(null);
  readonly busyId = signal<string | null>(null);

  /**
   * Draft answers keyed by attempt id, then by the field the agent could not
   * ground. Held here rather than in the template so an in-progress answer
   * survives a list refresh.
   */
  readonly answers = signal<Record<string, Record<string, string>>>({});

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.error.set('');
    this.service
      .listAttempts('escalated')
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (attempts) => {
          this.attempts.set(attempts);
          this.loading.set(false);
        },
        error: (err) => {
          this.loading.set(false);
          this.error.set(err?.error?.detail ?? 'Could not load the review queue.');
        },
      });
  }

  toggle(attemptId: string): void {
    this.expandedId.update((current) => (current === attemptId ? null : attemptId));
  }

  answerFor(attemptId: string, field: string): string {
    return this.answers()[attemptId]?.[field] ?? '';
  }

  setAnswer(attemptId: string, field: string, value: string): void {
    this.answers.update((all) => ({
      ...all,
      [attemptId]: { ...(all[attemptId] ?? {}), [field]: value },
    }));
  }

  canResume(attempt: SubmissionAttempt): boolean {
    const given = this.answers()[attempt.id] ?? {};
    return attempt.escalated_fields.every((field) => (given[field] ?? '').trim().length > 0);
  }

  resume(attempt: SubmissionAttempt): void {
    const given = this.answers()[attempt.id] ?? {};
    this.busyId.set(attempt.id);
    this.error.set('');
    this.notice.set('');
    this.service
      .resume(attempt.id, given)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.busyId.set(null);
          this.notice.set(
            'Queued for another attempt. Your answers were saved to your profile, so this question will not be asked again.',
          );
          this.clearAnswers(attempt.id);
          this.load();
        },
        error: (err) => {
          this.busyId.set(null);
          this.error.set(err?.error?.detail ?? 'Could not resume this application.');
        },
      });
  }

  abandon(attempt: SubmissionAttempt): void {
    this.busyId.set(attempt.id);
    this.error.set('');
    this.notice.set('');
    this.service
      .abandon(attempt.id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.busyId.set(null);
          this.notice.set('Application abandoned. It will not be submitted.');
          this.clearAnswers(attempt.id);
          this.load();
        },
        error: (err) => {
          this.busyId.set(null);
          this.error.set(err?.error?.detail ?? 'Could not abandon this application.');
        },
      });
  }

  private clearAnswers(attemptId: string): void {
    this.answers.update((all) => {
      const next = { ...all };
      delete next[attemptId];
      return next;
    });
  }
}
