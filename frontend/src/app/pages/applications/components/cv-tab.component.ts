import { Component, computed, inject, input, output, signal } from '@angular/core';
import { ApplicationsService } from '../../../core/services/applications.service';
import { ApplicationAggregate } from '../models/application-aggregate.model';

@Component({
  selector: 'app-cv-tab',
  standalone: true,
  templateUrl: './cv-tab.component.html',
  styleUrl: './cv-tab.component.scss',
})
export class CvTabComponent {
  private service = inject(ApplicationsService);

  aggregate = input.required<ApplicationAggregate>();
  changed = output<void>();

  cvLanguage = signal<'en' | 'es'>('en');
  running = signal(false);
  error = signal('');

  optimization = computed(() => this.aggregate().latest_optimization);
  hasMatch = computed(() => this.aggregate().latest_match !== null);

  run(): void {
    this.running.set(true);
    this.error.set('');
    this.service
      .generateOptimization(this.aggregate().id, { cv_language: this.cvLanguage() })
      .subscribe({
        next: () => {
          this.running.set(false);
          this.changed.emit();
        },
        error: (err) => {
          this.error.set(err?.error?.detail ?? 'Optimization failed');
          this.running.set(false);
        },
      });
  }

  downloadTex(): void {
    const opt = this.optimization();
    if (!opt) return;
    const blob = new Blob([opt.optimized_tex], { type: 'application/x-tex' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `cv_${opt.cv_language}.tex`;
    a.click();
    URL.revokeObjectURL(url);
  }

  pdfUrl = computed(() => this.service.cvPdfUrl(this.aggregate().id));

  onLangChange(ev: Event): void {
    this.cvLanguage.set((ev.target as HTMLSelectElement).value as 'en' | 'es');
  }
}
