import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  computed,
  inject,
  OnInit,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { ProfileService } from '../../core/services/profile.service';
import { CvSectionContentComponent } from './components/cv-section-content/cv-section-content.component';
import { ApplyProfileCardComponent } from './components/apply-profile-card/apply-profile-card.component';
import { ManualFieldsFormComponent } from './components/manual-fields-form/manual-fields-form.component';
import { CoverLetterLibraryComponent } from './components/cover-letter-library/cover-letter-library.component';
import { CoverLetterTemplatesComponent } from './components/cover-letter-templates/cover-letter-templates.component';
import { AccountComponent } from '../account/account.component';
import { PortfolioCardComponent } from './components/portfolio-card/portfolio-card.component';
import { NetworkCardComponent } from './components/network-card/network-card.component';

type ProfilePageTab = 'cv' | 'personal' | 'cover-letters' | 'account';

@Component({
  selector: 'app-profile',
  standalone: true,
  imports: [
    FormsModule,
    RouterLink,
    CvSectionContentComponent,
    ApplyProfileCardComponent,
    ManualFieldsFormComponent,
    CoverLetterLibraryComponent,
    CoverLetterTemplatesComponent,
    AccountComponent,
    PortfolioCardComponent,
    NetworkCardComponent,
  ],
  templateUrl: './profile.component.html',
  styleUrl: './profile.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ProfileComponent implements OnInit {
  private profileService = inject(ProfileService);
  private readonly destroyRef = inject(DestroyRef);

  pageTab = signal<ProfilePageTab>('cv');
  uploadMode = signal<'upload' | 'paste'>('upload');
  selectedFile = signal<File | null>(null);
  dragOver = signal(false);
  texContent = signal('');
  language = signal('en');
  loading = signal(false);
  initialLoading = signal(true);
  error = signal('');
  showUploadForm = signal(false);
  uploadIntent = signal<'add' | 'replace'>('add');
  editingPersonal = signal(false);
  translating = signal(false);
  translateWarning = signal('');

  profile = this.profileService.profile;
  profiles = this.profileService.profiles;
  activeLanguage = this.profileService.activeLanguage;
  uploadedLanguages = computed(() => Object.keys(this.profiles()));
  otherLanguage = computed(() => (this.activeLanguage() === 'es' ? 'en' : 'es'));

  constructor() {}

  ngOnInit(): void {
    this.profileService
      .listProfiles()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => this.initialLoading.set(false),
        error: () => {
          // Fallback to single profile fetch
          this.profileService
            .getCurrentProfile()
            .pipe(takeUntilDestroyed(this.destroyRef))
            .subscribe({
              next: () => this.initialLoading.set(false),
              error: () => this.initialLoading.set(false),
            });
        },
      });
  }

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
