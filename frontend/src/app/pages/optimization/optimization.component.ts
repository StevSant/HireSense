import { Component, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { OptimizationService } from '../../core/services/optimization.service';
import { OptimizationResult } from './models/optimization-result.model';

@Component({
  selector: 'app-optimization',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './optimization.component.html',
  styleUrl: './optimization.component.scss',
})
export class OptimizationComponent {
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

  constructor(private optimizationService: OptimizationService) {}

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
}
