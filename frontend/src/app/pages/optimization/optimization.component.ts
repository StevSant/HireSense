import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { OptimizationService } from '../../core/services/optimization.service';
import { ProfileService } from '../../core/services/profile.service';
import { IngestionService } from '../../core/services/ingestion.service';
import { OptimizationResult } from './models/optimization-result.model';

@Component({
  selector: 'app-optimization',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './optimization.component.html',
  styleUrl: './optimization.component.scss',
})
export class OptimizationComponent implements OnInit {
  private optimizationService = inject(OptimizationService);
  private profileService = inject(ProfileService);
  private ingestionService = inject(IngestionService);
  private route = inject(ActivatedRoute);

  matchId = signal('');
  jobId = signal('');
  cvId = signal('');
  originalTex = signal('');
  jobDescription = signal('');
  jobSkills = signal('');
  missingSkills = signal('');
  result = signal<OptimizationResult | null>(null);
  loading = signal(false);
  error = signal('');

  // File upload
  selectedFile = signal<File | null>(null);
  dragOver = signal(false);
  inputMode = signal<'profile' | 'paste' | 'file'>('profile');

  // Profile-based
  availableLanguages = computed(() => Object.keys(this.profileService.profiles()));
  selectedLanguage = signal('en');

  ngOnInit(): void {
    if (this.availableLanguages().length === 0) {
      this.profileService.listProfiles().subscribe({
        next: () => this.prefillFromProfile(),
        error: () => {},
      });
    } else {
      this.prefillFromProfile();
    }
    this.applyJobIdFromQuery();
  }

  private applyJobIdFromQuery(): void {
    const jobId = this.route.snapshot.queryParamMap.get('job_id');
    if (!jobId) return;
    this.ingestionService.getJob(jobId).subscribe({
      next: (job) => {
        this.jobId.set(job.id);
        this.jobDescription.set(job.description);
        this.jobSkills.set(job.skills.join(', '));
      },
      error: () => {},
    });
  }

  onLanguageChange(lang: string): void {
    this.selectedLanguage.set(lang);
    this.prefillFromProfile();
  }

  onInputModeChange(mode: 'profile' | 'paste' | 'file'): void {
    this.inputMode.set(mode);
    if (mode === 'profile') {
      this.prefillFromProfile();
    } else {
      this.originalTex.set('');
      this.selectedFile.set(null);
    }
  }

  private prefillFromProfile(): void {
    const profiles = this.profileService.profiles();
    const lang = this.selectedLanguage();
    const profile = profiles[lang] ?? Object.values(profiles)[0];
    if (!profile) {
      this.inputMode.set('paste');
      return;
    }
    this.selectedLanguage.set(profile.language);
    if (profile.raw_tex) {
      this.originalTex.set(profile.raw_tex);
    }
  }

  onDragOver(event: DragEvent): void {
    event.preventDefault();
    this.dragOver.set(true);
  }

  onDragLeave(event: DragEvent): void {
    event.preventDefault();
    this.dragOver.set(false);
  }

  onDrop(event: DragEvent): void {
    event.preventDefault();
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
    this.originalTex.set('');
  }

  private handleFile(file: File): void {
    const ext = file.name.split('.').pop()?.toLowerCase();
    if (ext !== 'tex') {
      this.error.set('Only .tex files are supported for optimization');
      return;
    }
    this.error.set('');
    this.selectedFile.set(file);
    // Read file content
    const reader = new FileReader();
    reader.onload = () => {
      this.originalTex.set(reader.result as string);
    };
    reader.readAsText(file);
  }

  optimize(): void {
    this.loading.set(true);
    this.error.set('');
    const payload = {
      match_id: this.matchId() || 'manual',
      job_id: this.jobId() || 'manual',
      cv_id: this.cvId() || 'manual',
      original_tex: this.originalTex(),
      job_description: this.jobDescription(),
      job_skills: this.jobSkills().split(',').map(s => s.trim()).filter(Boolean),
      missing_skills: this.missingSkills().split(',').map(s => s.trim()).filter(Boolean),
      recommendations: [],
    };
    this.optimizationService.optimize(payload).subscribe({
      next: (res) => {
        this.result.set(res);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(err.error?.detail || 'Optimization failed');
        this.loading.set(false);
      },
    });
  }

  downloadTex(): void {
    const tex = this.result()?.optimized_tex;
    if (!tex) return;
    const blob = new Blob([tex], { type: 'application/x-tex' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'optimized_cv.tex';
    a.click();
    URL.revokeObjectURL(url);
  }

  formatFileSize(bytes: number): string {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  }
}
