import { Component, DestroyRef, computed, inject, input, output, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ApplicationsService } from '../../../core/services/applications.service';
import { CvOptimizationRunnerService } from '../../../core/services/cv-optimization-runner.service';
import { ApplicationAggregate } from '../models/application-aggregate.model';

type ViewMode = 'changes' | 'full';

@Component({
  selector: 'app-cv-tab',
  standalone: true,
  templateUrl: './cv-tab.component.html',
  styleUrl: './cv-tab.component.scss',
})
export class CvTabComponent {
  private service = inject(ApplicationsService);
  private runner = inject(CvOptimizationRunnerService);
  private readonly destroyRef = inject(DestroyRef);

  aggregate = input.required<ApplicationAggregate>();
  changed = output<void>();

  cvLanguage = signal<'en' | 'es'>('en');
  viewMode = signal<ViewMode>('changes');
  copyFlash = signal(false);
  downloadingPdf = signal(false);
  downloadingOriginal = signal(false);
  downloadError = signal('');

  running = computed(() => this.runner.isRunning(this.aggregate().id));
  runnerError = computed(() => this.runner.lastError());
  optimization = computed(() => this.aggregate().latest_optimization);
  hasMatch = computed(() => this.aggregate().latest_match !== null);

  run(): void {
    this.downloadError.set('');
    this.runner.run(this.aggregate().id, this.cvLanguage());
  }

  setViewMode(mode: ViewMode): void {
    this.viewMode.set(mode);
  }

  async copyTex(): Promise<void> {
    const opt = this.optimization();
    if (!opt) return;
    try {
      await navigator.clipboard.writeText(opt.optimized_tex);
      this.copyFlash.set(true);
      setTimeout(() => this.copyFlash.set(false), 1800);
    } catch {
      this.downloadError.set('Clipboard access denied — use Download .tex instead.');
    }
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

  downloadPdf(): void {
    this.downloadingPdf.set(true);
    this.downloadError.set('');
    this.service.downloadCvPdf(this.aggregate().id).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (blob) => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `cv_${this.optimization()?.cv_language ?? 'en'}.pdf`;
        a.click();
        URL.revokeObjectURL(url);
        this.downloadingPdf.set(false);
      },
      error: (err) => {
        this.downloadError.set(err?.error?.detail ?? 'PDF download failed');
        this.downloadingPdf.set(false);
      },
    });
  }

  /** Compile and download the untouched profile CV — no optimization needed. */
  downloadOriginalPdf(): void {
    this.downloadingOriginal.set(true);
    this.downloadError.set('');
    this.service.downloadOriginalCvPdf(this.aggregate().id, this.cvLanguage()).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (blob) => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `cv_original_${this.cvLanguage()}.pdf`;
        a.click();
        URL.revokeObjectURL(url);
        this.downloadingOriginal.set(false);
      },
      error: (err) => {
        this.downloadError.set(err?.error?.detail ?? 'Original CV PDF download failed');
        this.downloadingOriginal.set(false);
      },
    });
  }

  onLangChange(ev: Event): void {
    this.cvLanguage.set((ev.target as HTMLSelectElement).value as 'en' | 'es');
  }
}
