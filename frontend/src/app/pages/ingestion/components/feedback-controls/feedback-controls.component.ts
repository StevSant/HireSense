import { ChangeDetectionStrategy, Component, inject, input, output, signal } from '@angular/core';
import { PreferenceService } from '../../../../core/services/preference.service';
import { FeedbackKind } from '../../models/feedback-kind.model';

interface FeedbackControl {
  kind: FeedbackKind;
  icon: string;
  label: string;
}

@Component({
  selector: 'app-feedback-controls',
  standalone: true,
  templateUrl: './feedback-controls.component.html',
  styleUrl: './feedback-controls.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FeedbackControlsComponent {
  private preferenceService = inject(PreferenceService);

  jobId = input.required<string>();
  /** Compact = icon-only, for list rows. Default shows labels (detail panel). */
  compact = input<boolean>(false);

  feedbackSubmitted = output<FeedbackKind>();

  pending = signal<FeedbackKind | null>(null);
  lastSent = signal<FeedbackKind | null>(null);
  failed = signal(false);

  readonly controls: FeedbackControl[] = [
    { kind: 'thumbs_up', icon: '👍', label: 'More relevant' },
    { kind: 'thumbs_down', icon: '👎', label: 'Less relevant' },
    { kind: 'not_interested', icon: '🚫', label: 'Not interested' },
    { kind: 'more_like_this', icon: '✨', label: 'More like this' },
  ];

  submit(kind: FeedbackKind): void {
    if (this.pending() !== null) return;
    this.pending.set(kind);
    this.failed.set(false);
    this.preferenceService.submitFeedback(this.jobId(), kind).subscribe({
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
