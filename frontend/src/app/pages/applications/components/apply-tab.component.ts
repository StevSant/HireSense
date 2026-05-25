import { Component, computed, inject, input, output, signal } from '@angular/core';
import { ApplicationsService } from '../../../core/services/applications.service';
import { ApplicationAggregate } from '../models/application-aggregate.model';

@Component({
  selector: 'app-apply-tab',
  standalone: true,
  templateUrl: './apply-tab.component.html',
  styleUrl: './apply-tab.component.scss',
})
export class ApplyTabComponent {
  private service = inject(ApplicationsService);

  aggregate = input.required<ApplicationAggregate>();
  changed = output<void>();

  cvLanguage = signal<'en' | 'es'>('en');
  tone = signal<'professional' | 'enthusiastic' | 'concise'>('professional');
  generating = signal(false);
  marking = signal(false);
  error = signal('');

  letter = computed(() => this.aggregate().latest_cover_letter);
  hasCv = computed(() => this.aggregate().latest_optimization !== null);
  isApplied = computed(() => this.aggregate().status === 'applied' || !!this.aggregate().applied_at);

  cvPdfUrl = computed(() => this.service.cvPdfUrl(this.aggregate().id));
  coverLetterPdfUrl = computed(() => this.service.coverLetterPdfUrl(this.aggregate().id));
  bundleUrl = computed(() => this.service.bundleUrl(this.aggregate().id));

  generate(): void {
    this.generating.set(true);
    this.error.set('');
    this.service
      .generateCoverLetter(this.aggregate().id, {
        cv_language: this.cvLanguage(),
        tone: this.tone(),
      })
      .subscribe({
        next: () => {
          this.generating.set(false);
          this.changed.emit();
        },
        error: (err) => {
          this.error.set(err?.error?.detail ?? 'Cover letter generation failed');
          this.generating.set(false);
        },
      });
  }

  openJobAndMarkApplied(): void {
    const url = this.aggregate().url;
    if (url) {
      window.open(url, '_blank', 'noopener');
    }
    this.markApplied();
  }

  markApplied(): void {
    this.marking.set(true);
    this.error.set('');
    this.service.markApplied(this.aggregate().id).subscribe({
      next: () => {
        this.marking.set(false);
        this.changed.emit();
      },
      error: (err) => {
        this.error.set(err?.error?.detail ?? 'Mark-applied failed');
        this.marking.set(false);
      },
    });
  }

  onLangChange(ev: Event): void {
    this.cvLanguage.set((ev.target as HTMLSelectElement).value as 'en' | 'es');
  }

  onToneChange(ev: Event): void {
    this.tone.set((ev.target as HTMLSelectElement).value as 'professional' | 'enthusiastic' | 'concise');
  }
}
