import { Component, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { environment } from '../../../environments/environment';
import { EvaluationResult } from '../../core/models/evaluation-result.model';
import { EvaluateRequest } from '../../core/models/evaluate-request.model';

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
  evaluationResult = signal<EvaluationResult | null>(null);
  evaluating = signal(false);

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

  evaluate(): void {
    this.evaluating.set(true);
    const req: EvaluateRequest = {
      job_title: this.jobDescription().split('\n')[0] || 'Unknown',
      company: 'Unknown',
      description: this.jobDescription(),
      skills: this.jobSkills().split(',').map(s => s.trim()).filter(Boolean),
    };
    this.http.post<EvaluationResult>(`${environment.apiUrl}/matching/evaluate`, req).subscribe({
      next: (res) => {
        this.evaluationResult.set(res);
        this.evaluating.set(false);
      },
      error: (err) => {
        this.error.set(err.error?.detail || 'Evaluation failed');
        this.evaluating.set(false);
      },
    });
  }

  dimensionLabel(dimension: string): string {
    const labels: Record<string, string> = {
      seniority_fit: 'Seniority Fit',
      compensation: 'Compensation',
      growth_potential: 'Growth Potential',
      culture_fit: 'Culture Fit',
      application_strength: 'Application Strength',
      interview_readiness: 'Interview Readiness',
    };
    return labels[dimension] || dimension.replace(/_/g, ' ');
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
