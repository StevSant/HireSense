import { Component, computed, inject, input, output, signal } from '@angular/core';
import { ApplicationsService } from '../../../core/services/applications.service';
import { ApplicationAggregate } from '../models/application-aggregate.model';
import { SkillChipsComponent } from './skill-chips.component';

@Component({
  selector: 'app-match-tab',
  standalone: true,
  imports: [SkillChipsComponent],
  templateUrl: './match-tab.component.html',
  styleUrl: './match-tab.component.scss',
})
export class MatchTabComponent {
  private service = inject(ApplicationsService);

  aggregate = input.required<ApplicationAggregate>();
  changed = output<void>();

  cvLanguage = signal<'en' | 'es'>('en');
  running = signal(false);
  error = signal('');

  match = computed(() => this.aggregate().latest_match);

  pct(score: number): string {
    return (score * 100).toFixed(0);
  }

  color(score: number): string {
    if (score >= 0.7) return '#16a34a';
    if (score >= 0.4) return '#ca8a04';
    return '#dc2626';
  }

  run(): void {
    this.running.set(true);
    this.error.set('');
    this.service.generateMatch(this.aggregate().id, this.cvLanguage()).subscribe({
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
