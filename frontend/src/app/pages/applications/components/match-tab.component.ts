import { Component, DestroyRef, computed, inject, input, output, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ApplicationsService } from '../../../core/services/applications.service';
import { ApplicationAggregate } from '../models/application-aggregate.model';
import { SkillChipsComponent } from './skill-chips.component';
import { scoreColor as toScoreColor } from '../../../core/utils/score-color';
import { formatScorePercent } from '../../../core/utils/format-score-percent';

@Component({
  selector: 'app-match-tab',
  standalone: true,
  imports: [SkillChipsComponent],
  templateUrl: './match-tab.component.html',
  styleUrl: './match-tab.component.scss',
})
export class MatchTabComponent {
  private service = inject(ApplicationsService);
  private readonly destroyRef = inject(DestroyRef);

  aggregate = input.required<ApplicationAggregate>();
  changed = output<void>();

  cvLanguage = signal<'en' | 'es'>('en');
  running = signal(false);
  error = signal('');

  match = computed(() => this.aggregate().latest_match);

  pct(score: number): string {
    return formatScorePercent(score, false);
  }

  color(score: number): string {
    return toScoreColor(score);
  }

  run(): void {
    this.running.set(true);
    this.error.set('');
    this.service.generateMatch(this.aggregate().id, this.cvLanguage()).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: () => {
        this.running.set(false);
        this.changed.emit();
      },
      error: (err) => {
        this.error.set(err?.error?.detail ?? 'Match failed');
        this.running.set(false);
      },
    });
  }

  onLangChange(ev: Event): void {
    this.cvLanguage.set((ev.target as HTMLSelectElement).value as 'en' | 'es');
  }
}
