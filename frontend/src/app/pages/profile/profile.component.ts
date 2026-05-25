import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { ProfileService } from '../../core/services/profile.service';
import { ApplicationsService } from '../../core/services/applications.service';
import { CoverLetterTemplatesService } from '../../core/services/cover-letter-templates.service';
import { CandidateProfile } from './models/candidate-profile.model';
import { CoverLetterTemplate } from './models/cover-letter-template.model';
import { CoverLetterLibraryItem } from '../applications/models/cover-letter-library-item.model';

type ProfilePageTab = 'cv' | 'personal' | 'cover-letters';

@Component({
  selector: 'app-profile',
  standalone: true,
  imports: [FormsModule, RouterLink],
  templateUrl: './profile.component.html',
  styleUrl: './profile.component.scss',
})
export class ProfileComponent implements OnInit {
  private profileService = inject(ProfileService);
  private applicationsService = inject(ApplicationsService);
  private templatesService = inject(CoverLetterTemplatesService);

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

  editingPersonal = signal(false);
  editName = signal('');
  editLocation = signal('');
  editLinkedin = signal('');
  editGithub = signal('');
  editPortfolio = signal('');
  savingPersonal = signal(false);
  personalError = signal('');

  coverLetters = signal<CoverLetterLibraryItem[] | null>(null);
  coverLettersLoading = signal(false);
  coverLettersError = signal('');
  copiedId = signal<string | null>(null);

  templatesLoading = signal(false);
  templatesError = signal('');
  templates = this.templatesService.templates;
  templatesLoaded = signal(false);
  editingTemplateId = signal<string | null>(null); // null = not editing; 'new' = new draft
  templateName = signal('');
  templateBody = signal('');
  templateTone = signal('professional');
  templateLanguage = signal('en');
  savingTemplate = signal(false);

  profile = this.profileService.profile;
  profiles = this.profileService.profiles;
  activeLanguage = this.profileService.activeLanguage;
  uploadedLanguages = computed(() => Object.keys(this.profiles()));

  effectiveName = computed(() => {
    const p = this.profile();
    return p ? (p.name_override || p.name || '') : '';
  });

  effectiveLocation = computed(() => {
    const p = this.profile();
    return p ? (p.location_override || p.location || '') : '';
  });

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

  selectTab(tab: ProfilePageTab): void {
    this.pageTab.set(tab);
    if (tab === 'cover-letters') {
      this.loadCoverLetters();
      this.loadTemplates();
    }
  }

  loadTemplates(): void {
    if (this.templatesLoaded() || this.templatesLoading()) return;
    this.templatesLoading.set(true);
    this.templatesError.set('');
    this.templatesService.list().subscribe({
      next: () => {
        this.templatesLoaded.set(true);
        this.templatesLoading.set(false);
      },
      error: (err) => {
        this.templatesError.set(err.error?.detail || 'Failed to load templates');
        this.templatesLoading.set(false);
      },
    });
  }

  startNewTemplate(): void {
    this.editingTemplateId.set('new');
    this.templateName.set('');
    this.templateBody.set('');
    this.templateTone.set('professional');
    this.templateLanguage.set('en');
    this.templatesError.set('');
  }

  startEditTemplate(t: CoverLetterTemplate): void {
    this.editingTemplateId.set(t.id);
    this.templateName.set(t.name);
    this.templateBody.set(t.body);
    this.templateTone.set(t.tone);
    this.templateLanguage.set(t.language);
    this.templatesError.set('');
  }

  cancelEditTemplate(): void {
    this.editingTemplateId.set(null);
    this.templatesError.set('');
  }

  saveTemplate(): void {
    if (!this.templateName().trim() || !this.templateBody().trim()) {
      this.templatesError.set('Name and body are required');
      return;
    }
    this.savingTemplate.set(true);
    this.templatesError.set('');
    const editingId = this.editingTemplateId();
    const payload = {
      name: this.templateName().trim(),
      body: this.templateBody(),
      tone: this.templateTone(),
      language: this.templateLanguage(),
    };
    const obs =
      editingId && editingId !== 'new'
        ? this.templatesService.update(editingId, payload)
        : this.templatesService.create(payload);
    obs.subscribe({
      next: () => {
        this.savingTemplate.set(false);
        this.editingTemplateId.set(null);
      },
      error: (err) => {
        this.templatesError.set(err.error?.detail || 'Failed to save template');
        this.savingTemplate.set(false);
      },
    });
  }

  deleteTemplate(t: CoverLetterTemplate): void {
    if (!confirm(`Delete template "${t.name}"?`)) return;
    this.templatesService.delete(t.id).subscribe({
      error: (err) => {
        this.templatesError.set(err.error?.detail || 'Failed to delete template');
      },
    });
  }

  startEditPersonal(): void {
    const p = this.profile();
    if (!p) return;
    this.editName.set(p.name_override ?? '');
    this.editLocation.set(p.location_override ?? '');
    this.editLinkedin.set(p.linkedin_url ?? '');
    this.editGithub.set(p.github_url ?? '');
    this.editPortfolio.set(p.portfolio_url ?? '');
    this.personalError.set('');
    this.editingPersonal.set(true);
  }

  cancelEditPersonal(): void {
    this.editingPersonal.set(false);
    this.personalError.set('');
  }

  savePersonal(): void {
    const p = this.profile();
    if (!p) return;
    this.savingPersonal.set(true);
    this.personalError.set('');
    const patch = {
      name_override: this.editName().trim() || null,
      location_override: this.editLocation().trim() || null,
      linkedin_url: this.editLinkedin().trim() || null,
      github_url: this.editGithub().trim() || null,
      portfolio_url: this.editPortfolio().trim() || null,
    };
    this.profileService.updateProfile(p.id, patch).subscribe({
      next: () => {
        this.savingPersonal.set(false);
        this.editingPersonal.set(false);
      },
      error: (err) => {
        this.personalError.set(err.error?.detail || 'Failed to update profile');
        this.savingPersonal.set(false);
      },
    });
  }

  urlLabel(url: string): string {
    try {
      const u = new URL(url);
      return u.host + u.pathname.replace(/\/$/, '');
    } catch {
      return url;
    }
  }

  loadCoverLetters(): void {
    if (this.coverLetters() !== null || this.coverLettersLoading()) return;
    this.coverLettersLoading.set(true);
    this.coverLettersError.set('');
    this.applicationsService.listAllCoverLetters().subscribe({
      next: (items) => {
        this.coverLetters.set(items);
        this.coverLettersLoading.set(false);
      },
      error: (err) => {
        this.coverLettersError.set(err.error?.detail || 'Failed to load cover letters');
        this.coverLettersLoading.set(false);
      },
    });
  }

  copyBody(item: CoverLetterLibraryItem): void {
    navigator.clipboard.writeText(item.body).then(() => {
      this.copiedId.set(item.id);
      setTimeout(() => {
        if (this.copiedId() === item.id) this.copiedId.set(null);
      }, 1500);
    });
  }

  relativeTime(iso: string): string {
    const then = new Date(iso).getTime();
    if (isNaN(then)) return '';
    const diff = Date.now() - then;
    const minute = 60_000, hour = 60 * minute, day = 24 * hour;
    if (diff < hour) return `${Math.max(1, Math.round(diff / minute))}m ago`;
    if (diff < day) return `${Math.round(diff / hour)}h ago`;
    if (diff < 30 * day) return `${Math.round(diff / day)}d ago`;
    if (diff < 365 * day) return `${Math.round(diff / (30 * day))}mo ago`;
    return `${Math.round(diff / (365 * day))}y ago`;
  }
}
