import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ProfileService } from '../../core/services/profile.service';
import { CandidateProfile } from './models/candidate-profile.model';

@Component({
  selector: 'app-profile',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './profile.component.html',
  styleUrl: './profile.component.scss',
})
export class ProfileComponent implements OnInit {
  private profileService = inject(ProfileService);

  activeTab = signal<'upload' | 'paste'>('upload');
  selectedFile = signal<File | null>(null);
  dragOver = signal(false);
  texContent = signal('');
  language = signal('en');
  profile = this.profileService.profile;
  loading = signal(false);
  initialLoading = signal(true);
  error = signal('');

  constructor() {}

  ngOnInit(): void {
    if (!this.profile()) {
      this.profileService.getCurrentProfile().subscribe({
        next: () => {
          this.initialLoading.set(false);
        },
        error: () => {
          this.initialLoading.set(false);
        },
      });
    } else {
      this.initialLoading.set(false);
    }
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
        },
        error: (err) => {
          this.error.set(err.error?.detail || 'Failed to parse CV');
          this.loading.set(false);
        },
      });
  }

  resetProfile(): void {
    this.profileService.profile.set(null);
    this.selectedFile.set(null);
    this.texContent.set('');
    this.error.set('');
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
