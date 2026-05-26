import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { ProfileService } from '../../core/services/profile.service';
import { CandidateProfile } from './models/candidate-profile.model';
import { CvSectionContentComponent } from './components/cv-section-content/cv-section-content.component';
import { ManualFieldsFormComponent } from './components/manual-fields-form/manual-fields-form.component';
import { CoverLetterLibraryComponent } from './components/cover-letter-library/cover-letter-library.component';
import { CoverLetterTemplatesComponent } from './components/cover-letter-templates/cover-letter-templates.component';

type ProfilePageTab = 'cv' | 'personal' | 'cover-letters';

@Component({
  selector: 'app-profile',
  standalone: true,
  imports: [
    FormsModule,
    RouterLink,
    CvSectionContentComponent,
    ManualFieldsFormComponent,
    CoverLetterLibraryComponent,
    CoverLetterTemplatesComponent,
  ],
  templateUrl: './profile.component.html',
  styleUrl: './profile.component.scss',
})
export class ProfileComponent implements OnInit {
  private profileService = inject(ProfileService);

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

  profile = this.profileService.profile;
  profiles = this.profileService.profiles;
  activeLanguage = this.profileService.activeLanguage;
  uploadedLanguages = computed(() => Object.keys(this.profiles()));

  constructor() {}

  ngOnInit(): void {
    this.profileService.listProfiles().subscribe({
      next: () => this.initialLoading.set(false),
      error: () => {
        // Fallback to single profile fetch
        this.profileService.getCurrentProfile().subscribe({
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
    // Pre-select a language that hasn't been uploaded yet
    const uploaded = this.uploadedLanguages();
    if (!uploaded.includes('es')) {
      this.language.set('es');
    } else if (!uploaded.includes('en')) {
      this.language.set('en');
    }
    this.showUploadForm.set(true);
  }

  cancelUpload(): void {
    this.showUploadForm.set(false);
    this.selectedFile.set(null);
    this.texContent.set('');
    this.error.set('');
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
    this.profileService.uploadFile(file, this.language()).subscribe({
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
