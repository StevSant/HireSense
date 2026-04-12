import { Component, signal } from '@angular/core';
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
export class ProfileComponent {
  texContent = signal('');
  language = signal('en');
  profile = signal<CandidateProfile | null>(null);
  loading = signal(false);
  error = signal('');

  constructor(private profileService: ProfileService) {}

  uploadCV(): void {
    if (!this.texContent().trim()) return;
    this.loading.set(true);
    this.error.set('');
    this.profileService
      .uploadCV({
        tex_content: this.texContent(),
        language: this.language(),
      })
      .subscribe({
        next: (res) => {
          this.profile.set(res);
          this.loading.set(false);
        },
        error: (err) => {
          this.error.set(err.error?.detail || 'Failed to parse CV');
          this.loading.set(false);
        },
      });
  }
}
