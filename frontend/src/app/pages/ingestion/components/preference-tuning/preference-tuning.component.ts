import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
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

  explanation = signal<PreferenceExplanation | null>(null);
  expanded = signal(false);
  resetting = signal(false);

  toggle(): void {
    const next = !this.expanded();
    this.expanded.set(next);
    if (next) this.load();
  }

  load(): void {
    this.preferenceService.explain().subscribe({
      next: (e) => this.explanation.set(e),
      error: () => this.explanation.set(null),
    });
  }

  reset(): void {
    if (!confirm('Reset learned preferences? This clears all feedback-based tuning.')) return;
    this.resetting.set(true);
    this.preferenceService.reset().subscribe({
      next: () => {
        this.resetting.set(false);
        this.load();
      },
      error: () => this.resetting.set(false),
    });
  }
}
