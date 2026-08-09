import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  computed,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { ProfileService } from '../../../../core/services/profile.service';
import { CvSectionContentComponent } from '../../components/cv-section-content/cv-section-content.component';

/**
 * Profile → CV.
 *
 * Owns everything to do with the CV document itself: upload (file or LaTeX),
 * the per-language variants, translation and PDF download.
 */
@Component({
  selector: 'app-profile-cv-tab',
  standalone: true,
  imports: [FormsModule, CvSectionContentComponent],
  templateUrl: './profile-cv-tab.component.html',
  styleUrl: './profile-cv-tab.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ProfileCvTabComponent {
  private profileService = inject(ProfileService);
  private readonly destroyRef = inject(DestroyRef);

  uploadMode = signal<'upload' | 'paste'>('upload');
  selectedFile = signal<File | null>(null);
  dragOver = signal(false);
  texContent = signal('');
  language = signal('en');
  loading = signal(false);
  error = signal('');
  showUploadForm = signal(false);
  uploadIntent = signal<'add' | 'replace'>('add');
  translating = signal(false);
  translateWarning = signal('');
  translateCompileError = signal('');

  profile = this.profileService.profile;
  profiles = this.profileService.profiles;
  activeLanguage = this.profileService.activeLanguage;
  initialLoading = computed(() => !this.profileService.loaded());
  uploadedLanguages = computed(() => Object.keys(this.profiles()));
  otherLanguage = computed(() => (this.activeLanguage() === 'es' ? 'en' : 'es'));

  switchLanguage(lang: string): void {
    this.profileService.activeLanguage.set(lang);
  }

  addAnotherLanguage(): void {
    this.uploadIntent.set('add');
    // Pre-select a language that hasn't been uploaded yet
    const uploaded = this.uploadedLanguages();
    if (!uploaded.includes('es')) {
      this.language.set('es');
    } else if (!uploaded.includes('en')) {
      this.language.set('en');
    }
    this.showUploadForm.set(true);
  }

  replaceCv(): void {
    this.language.set(this.activeLanguage());
    this.uploadIntent.set('replace');
    this.selectedFile.set(null);
    this.error.set('');
    this.showUploadForm.set(true);
  }

  cancelUpload(): void {
    this.showUploadForm.set(false);
    this.selectedFile.set(null);
    this.texContent.set('');
    this.error.set('');
    this.uploadIntent.set('add');
  }

  onDragOver(event: DragEvent): void {
    event.preventDefault();
    event.stopPropagation();
    this.dragOver.set(true);
  }

  onDragLeave(event: DragEvent): void {
    event.preventDefault();
    event.stopPropagation();
    this.dragOver.set(false);
  }

  onDrop(event: DragEvent): void {
    event.preventDefault();
    event.stopPropagation();
    this.dragOver.set(false);
    const files = event.dataTransfer?.files;
    if (files && files.length > 0) {
      this.handleFile(files[0]);
    }
  }

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      this.handleFile(input.files[0]);
    }
  }

  removeFile(): void {
    this.selectedFile.set(null);
  }

  uploadFile(): void {
    const file = this.selectedFile();
    if (!file) return;
    this.loading.set(true);
    this.error.set('');
    this.profileService
      .uploadFile(file, this.language())
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.loading.set(false);
          this.showUploadForm.set(false);
          this.selectedFile.set(null);
        },
        error: (err) => {
          this.error.set(err.error?.detail || 'Failed to parse file');
          this.loading.set(false);
        },
      });
  }

  uploadLatex(): void {
    if (!this.texContent().trim()) return;
    this.loading.set(true);
    this.error.set('');
    this.profileService
      .uploadCV({
        tex_content: this.texContent(),
        language: this.language(),
      })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.loading.set(false);
          this.showUploadForm.set(false);
          this.texContent.set('');
        },
        error: (err) => {
          this.error.set(err.error?.detail || 'Failed to parse CV');
          this.loading.set(false);
        },
      });
  }

  translateToOther(): void {
    const target = this.otherLanguage();
    this.translating.set(true);
    this.translateWarning.set('');
    this.translateCompileError.set('');
    this.profileService
      .translate(target)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.translating.set(false);
          if (!res.pdf_ok) {
            this.translateWarning.set(
              'Translated, but the PDF did not compile — review the LaTeX.',
            );
            this.translateCompileError.set(res.compile_error ?? '');
          }
        },
        error: (err) => {
          this.translateWarning.set(err.error?.detail || 'Translation failed');
          this.translating.set(false);
        },
      });
  }

  downloadPdf(language: string): void {
    this.profileService
      .downloadCvPdf(language)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (blob) => {
          const url = URL.createObjectURL(blob);
          const anchor = document.createElement('a');
          anchor.href = url;
          anchor.download = `cv_${language}.pdf`;
          anchor.click();
          URL.revokeObjectURL(url);
        },
        error: (err) => this.error.set(err.error?.detail || 'Failed to download PDF'),
      });
  }

  private handleFile(file: File): void {
    const ext = file.name.split('.').pop()?.toLowerCase();
    if (ext !== 'pdf' && ext !== 'tex') {
      this.error.set('Only PDF and .tex files are supported');
      return;
    }
    this.error.set('');
    this.selectedFile.set(file);
  }

  formatFileSize(bytes: number): string {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  }
}
