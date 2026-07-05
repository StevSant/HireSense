import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  inject,
  input,
  output,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { PreferenceService } from '../../../../core/services/preference.service';
import { FeedbackControl } from '../../models/feedback-control.model';
import { FeedbackKind } from '../../models/feedback-kind.model';

@Component({
  selector: 'app-feedback-controls',
  standalone: true,
  templateUrl: './feedback-controls.component.html',
  styleUrl: './feedback-controls.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FeedbackControlsComponent {
  private preferenceService = inject(PreferenceService);
  private destroyRef = inject(DestroyRef);

  jobId = input.required<string>();
  /** Compact = icon-only, for list rows. Default shows labels (detail panel). */
  compact = input<boolean>(false);

  feedbackSubmitted = output<FeedbackKind>();

  pending = signal<FeedbackKind | null>(null);
  lastSent = signal<FeedbackKind | null>(null);
  failed = signal(false);

  readonly controls: FeedbackControl[] = [
    { kind: 'thumbs_up', icon: 'thumb-up', label: 'More relevant' },
    { kind: 'thumbs_down', icon: 'thumb-down', label: 'Less relevant' },
    { kind: 'not_interested', icon: 'ban', label: 'Not interested' },
    { kind: 'more_like_this', icon: 'sparkle', label: 'More like this' },
  ];

  submit(kind: FeedbackKind): void {
    if (this.pending() !== null) return;
    this.pending.set(kind);
    this.failed.set(false);
    this.preferenceService
      .submitFeedback(this.jobId(), kind)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.pending.set(null);
          this.lastSent.set(kind);
          this.feedbackSubmitted.emit(kind);
        },
        error: () => {
          this.pending.set(null);
          this.failed.set(true);
        },
      });
  }
}
