import { Component, DestroyRef, computed, inject, input, output, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ApplicationsService } from '../../../core/services/applications.service';
import { CoverLetterRunnerService } from '../../../core/services/cover-letter-runner.service';
import { ApplicationAggregate } from '../models/application-aggregate.model';
import { CoverLetterTone } from '../models/cover-letter-tone.model';

@Component({
  selector: 'app-apply-tab',
  standalone: true,
  imports: [DatePipe],
  templateUrl: './apply-tab.component.html',
  styleUrl: './apply-tab.component.scss',
})
export class ApplyTabComponent {
  private service = inject(ApplicationsService);
  private runner = inject(CoverLetterRunnerService);
  private readonly destroyRef = inject(DestroyRef);

  aggregate = input.required<ApplicationAggregate>();
  changed = output<void>();

  cvLanguage = signal<'en' | 'es'>('en');
  tone = signal<CoverLetterTone>('professional');
  marking = signal(false);
  copyFlash = signal(false);
  error = signal('');

  generating = computed(() => this.runner.isRunning(this.aggregate().id));
  runnerError = computed(() => this.runner.lastError());
  letter = computed(() => this.aggregate().latest_cover_letter);
  hasCv = computed(() => this.aggregate().latest_optimization !== null);
  isApplied = computed(
    () => this.aggregate().status === 'applied' || !!this.aggregate().applied_at,
  );

  downloadingCv = signal(false);
  downloadingLetter = signal(false);
  downloadingBundle = signal(false);

  generate(): void {
    this.error.set('');
    this.runner.run(this.aggregate().id, this.cvLanguage(), this.tone());
  }

  async copyLetter(): Promise<void> {
    const body = this.letter()?.body;
    if (!body) return;
    try {
      await navigator.clipboard.writeText(body);
      this.copyFlash.set(true);
      setTimeout(() => this.copyFlash.set(false), 1800);
    } catch {
      this.error.set('Clipboard access denied — use Download or select & copy.');
    }
  }

  downloadCv(): void {
    this.downloadingCv.set(true);
    this.error.set('');
    // Prefer the tailored optimization when available, fall back to the
    // untouched profile CV so the user can still grab a PDF mid-process.
    const obs = this.hasCv()
      ? this.service.downloadCvPdf(this.aggregate().id)
      : this.service.downloadOriginalCvPdf(this.aggregate().id, this.cvLanguage());
    obs.pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (blob) => {
        const suffix = this.hasCv() ? '' : '_original';
        this.triggerDownload(blob, `cv${suffix}_${this.safeCompany()}.pdf`);
        this.downloadingCv.set(false);
      },
      error: (err) => {
        this.error.set(err?.error?.detail ?? 'CV PDF download failed');
        this.downloadingCv.set(false);
      },
    });
  }

  downloadLetter(): void {
    this.downloadingLetter.set(true);
    this.error.set('');
    this.service
      .downloadCoverLetterPdf(this.aggregate().id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (blob) => {
          this.triggerDownload(blob, `cover_letter_${this.safeCompany()}.pdf`);
          this.downloadingLetter.set(false);
        },
        error: (err) => {
          this.error.set(err?.error?.detail ?? 'Cover letter PDF download failed');
          this.downloadingLetter.set(false);
        },
      });
  }

  downloadBundle(): void {
    this.downloadingBundle.set(true);
    this.error.set('');
    this.service
      .downloadBundle(this.aggregate().id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (blob) => {
          this.triggerDownload(blob, `application_${this.safeCompany()}.zip`);
          this.downloadingBundle.set(false);
        },
        error: (err) => {
          this.error.set(err?.error?.detail ?? 'Bundle download failed');
          this.downloadingBundle.set(false);
        },
      });
  }

  private triggerDownload(blob: Blob, filename: string): void {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  private safeCompany(): string {
    return (this.aggregate().company || 'company').replace(/[^a-zA-Z0-9]+/g, '_').slice(0, 40);
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
    this.service
      .markApplied(this.aggregate().id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
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
    this.tone.set((ev.target as HTMLSelectElement).value as CoverLetterTone);
  }
}
