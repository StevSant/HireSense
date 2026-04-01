import { Component, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { environment } from '../../../environments/environment';

interface ScoreBreakdown {
  semantic_score: number;
  skill_score: number;
  experience_score: number;
  language_score: number;
}

interface MatchResult {
  id: string;
  job_id: string;
  cv_id: string;
  overall_score: number;
  breakdown: ScoreBreakdown;
  matched_skills: string[];
  missing_skills: string[];
  pros: string[];
  cons: string[];
  recommendations: string[];
}

@Component({
  selector: 'app-matching',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './matching.component.html',
  styleUrl: './matching.component.scss',
})
export class MatchingComponent {
  jobDescription = signal('');
  jobSkills = signal('');
  cvSummary = signal('');
  cvSkills = signal('');
  result = signal<MatchResult | null>(null);
  loading = signal(false);
  error = signal('');

  constructor(private http: HttpClient) {}

  analyze(): void {
    this.loading.set(true);
    this.error.set('');
    const payload = {
      job_id: 'manual',
      cv_id: 'manual',
      job_description: this.jobDescription(),
      job_skills: this.jobSkills().split(',').map(s => s.trim()).filter(Boolean),
      cv_summary: this.cvSummary(),
      cv_skills: this.cvSkills().split(',').map(s => s.trim()).filter(Boolean),
    };
    this.http.post<MatchResult>(`${environment.apiUrl}/matching/analyze`, payload).subscribe({
      next: (res) => {
        this.result.set(res);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(err.error?.detail || 'Analysis failed');
        this.loading.set(false);
      },
    });
  }

  scoreColor(score: number): string {
    if (score >= 0.7) return '#16a34a';
    if (score >= 0.4) return '#ca8a04';
    return '#dc2626';
  }

  scorePercent(score: number): string {
    return (score * 100).toFixed(0);
  }
}
