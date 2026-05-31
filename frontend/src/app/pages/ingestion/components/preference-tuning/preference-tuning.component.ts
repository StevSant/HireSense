import { ChangeDetectionStrategy, Component, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { KeyValuePipe } from '@angular/common';
import { PreferenceService } from '../../../../core/services/preference.service';
import { PreferenceExplanation } from '../../models/preference-explanation.model';

@Component({
  selector: 'app-preference-tuning',
  standalone: true,
  imports: [KeyValuePipe],
  templateUrl: './preference-tuning.component.html',
  styleUrl: './preference-tuning.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PreferenceTuningComponent {
  private preferenceService = inject(PreferenceService);
  private destroyRef = inject(DestroyRef);

  explanation = signal<PreferenceExplanation | null>(null);
  expanded = signal(false);
  resetting = signal(false);

  toggle(): void {
    const next = !this.expanded();
    this.expanded.set(next);
    if (next) this.load();
  }

  private load(): void {
    this.preferenceService
      .explain()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (e) => this.explanation.set(e),
        error: () => this.explanation.set(null),
      });
  }

  reset(): void {
    if (!confirm('Reset learned preferences? This clears all feedback-based tuning.')) return;
    this.resetting.set(true);
    this.preferenceService
      .reset()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.resetting.set(false);
          this.load();
        },
        error: () => this.resetting.set(false),
      });
  }
}
