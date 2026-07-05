import { Component, DestroyRef, computed, effect, inject, input, output, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { ApplicationsService } from '../../../core/services/applications.service';
import { CvOptimizationRunnerService } from '../../../core/services/cv-optimization-runner.service';
import { ApplicationAggregate } from '../models/application-aggregate.model';

type ViewMode = 'changes' | 'full';
type PreviewSource = 'original' | 'optimized';

@Component({
  selector: 'app-cv-tab',
  standalone: true,
  templateUrl: './cv-tab.component.html',
  styleUrl: './cv-tab.component.scss',
})
export class CvTabComponent {
  private service = inject(ApplicationsService);
  private runner = inject(CvOptimizationRunnerService);
  private sanitizer = inject(DomSanitizer);
  private readonly destroyRef = inject(DestroyRef);

  aggregate = input.required<ApplicationAggregate>();
  changed = output<void>();

  cvLanguage = signal<'en' | 'es'>('en');
  viewMode = signal<ViewMode>('changes');
  copyFlash = signal(false);
  downloadingPdf = signal(false);
  downloadingOriginal = signal(false);
  downloadError = signal('');

  previewSource = signal<PreviewSource>('optimized');
  previewUrl = signal<SafeResourceUrl | null>(null);
  previewLoading = signal(false);
  previewError = signal('');
  private objectUrl: string | null = null;

  running = computed(() => this.runner.isRunning(this.aggregate().id));
  runnerError = computed(() => this.runner.lastError());
  optimization = computed(() => this.aggregate().latest_optimization);
  hasMatch = computed(() => this.aggregate().latest_match !== null);

  /** Without an optimization only the Original CV can be previewed. */
  effectivePreviewSource = computed<PreviewSource>(() =>
    this.optimization() ? this.previewSource() : 'original',
  );

  /**
   * Everything the inline preview depends on. Reading `optimization()?.id`
   * means a re-run (new optimization) refreshes the frame even when the
   * selected source doesn't change.
   */
  private previewRequest = computed(() => ({
    appId: this.aggregate().id,
    original: this.effectivePreviewSource() === 'original',
    language: this.cvLanguage(),
    optId: this.optimization()?.id ?? null,
  }));

  constructor() {
    effect(() => {
      const req = this.previewRequest();
      this.loadPreview(req.appId, req.original, req.language);
    });
    this.destroyRef.onDestroy(() => this.revokeObjectUrl());
  }

  setPreviewSource(source: PreviewSource): void {
    this.previewSource.set(source);
  }

  private loadPreview(appId: string, original: boolean, language: 'en' | 'es'): void {
    this.previewLoading.set(true);
    this.previewError.set('');
    this.service
      .fetchCvPdf(appId, { original, language })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (blob) => {
          this.revokeObjectUrl();
          this.objectUrl = URL.createObjectURL(blob);
          this.previewUrl.set(this.sanitizer.bypassSecurityTrustResourceUrl(this.objectUrl));
          this.previewLoading.set(false);
        },
        error: (err: unknown) => {
          this.revokeObjectUrl();
          this.previewUrl.set(null);
          this.previewLoading.set(false);
          void this.setPreviewError(err);
        },
      });
  }

  private async setPreviewError(err: unknown): Promise<void> {
    const detail = await this.extractErrorDetail(err);
    this.previewError.set(detail ?? 'Could not render the CV preview.');
  }

  /**
   * Pull the FastAPI `detail` out of an error. With `responseType: 'blob'`
   * the error body arrives as a Blob, so it must be read and parsed.
   */
  private async extractErrorDetail(err: unknown): Promise<string | null> {
    const body = (err as { error?: unknown } | null)?.error;
    if (body instanceof Blob) {
      try {
        const parsed: unknown = JSON.parse(await body.text());
        const detail = (parsed as { detail?: unknown })?.detail;
        return typeof detail === 'string' ? detail : null;
      } catch {
        return null;
      }
    }
    const detail = (body as { detail?: unknown } | null)?.detail;
    return typeof detail === 'string' ? detail : null;
  }

  private revokeObjectUrl(): void {
    if (this.objectUrl) {
      URL.revokeObjectURL(this.objectUrl);
      this.objectUrl = null;
    }
  }

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
