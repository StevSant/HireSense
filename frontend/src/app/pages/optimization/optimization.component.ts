import { Component, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { environment } from '../../../environments/environment';

interface SectionChange {
  section_name: string;
  original: string;
  optimized: string;
  reason: string;
}

interface OptimizationResult {
  id: string;
  match_id: string;
  changes: SectionChange[];
  original_tex: string;
  optimized_tex: string;
  improvement_summary: string | null;
}

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

  constructor(private http: HttpClient) {}

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
    this.http.post<OptimizationResult>(`${environment.apiUrl}/optimization/optimize`, payload).subscribe({
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
