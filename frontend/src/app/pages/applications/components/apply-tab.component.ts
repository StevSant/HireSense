import { Component, OnInit, computed, inject, input, output, signal } from '@angular/core';
import { ApplicationsService } from '../../../core/services/applications.service';
import { CoverLetterTemplatesService } from '../../../core/services/cover-letter-templates.service';
import { ApplicationAggregate } from '../models/application-aggregate.model';

@Component({
  selector: 'app-apply-tab',
  standalone: true,
  templateUrl: './apply-tab.component.html',
  styleUrl: './apply-tab.component.scss',
})
export class ApplyTabComponent implements OnInit {
  private service = inject(ApplicationsService);
  private templatesService = inject(CoverLetterTemplatesService);

  aggregate = input.required<ApplicationAggregate>();
  changed = output<void>();

  cvLanguage = signal<'en' | 'es'>('en');
  tone = signal<'professional' | 'enthusiastic' | 'concise'>('professional');
  templateId = signal<string>('');
  generating = signal(false);
  marking = signal(false);
  error = signal('');

  templates = this.templatesService.templates;
  filteredTemplates = computed(() =>
    (this.templates() ?? []).filter((t) => t.language === this.cvLanguage()),
  );

  ngOnInit(): void {
    if (this.templates() === null) {
      this.templatesService.list().subscribe();
    }
  }

  letter = computed(() => this.aggregate().latest_cover_letter);
  hasCv = computed(() => this.aggregate().latest_optimization !== null);
  isApplied = computed(() => this.aggregate().status === 'applied' || !!this.aggregate().applied_at);

  downloadingCv = signal(false);
  downloadingLetter = signal(false);
  downloadingBundle = signal(false);

  downloadCv(): void {
    this.downloadingCv.set(true);
    this.error.set('');
    this.service.downloadCvPdf(this.aggregate().id).subscribe({
      next: (blob) => {
        this.triggerDownload(blob, `cv_${this.safeCompany()}.pdf`);
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
    this.service.downloadCoverLetterPdf(this.aggregate().id).subscribe({
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
    this.service.downloadBundle(this.aggregate().id).subscribe({
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

  generate(): void {
    this.generating.set(true);
    this.error.set('');
    const payload: { cv_language: string; tone?: string; template_id?: string } = {
      cv_language: this.cvLanguage(),
      tone: this.tone(),
    };
    if (this.templateId()) {
      payload.template_id = this.templateId();
    }
    this.service.generateCoverLetter(this.aggregate().id, payload).subscribe({
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

  onTemplateChange(ev: Event): void {
    this.templateId.set((ev.target as HTMLSelectElement).value);
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
