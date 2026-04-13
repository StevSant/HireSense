import { Component, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatchingService } from '../../core/services/matching.service';
import { ProfileService } from '../../core/services/profile.service';
import { IngestionService } from '../../core/services/ingestion.service';
import { NormalizedJob } from '../ingestion/models/normalized-job.model';
import { EvaluateRequest } from './models/evaluate-request.model';
import { EvaluationResult } from './models/evaluation-result.model';
import { MatchResult } from './models/match-result.model';

@Component({
  selector: 'app-matching',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './matching.component.html',
  styleUrl: './matching.component.scss',
})
export class MatchingComponent implements OnInit {
  jobDescription = signal('');
  jobSkills = signal('');
  cvSummary = signal('');
  cvSkills = signal('');
  result = signal<MatchResult | null>(null);
  loading = signal(false);
  error = signal('');
  evaluationResult = signal<EvaluationResult | null>(null);
  evaluating = signal(false);

  jobs = signal<NormalizedJob[]>([]);
  selectedJobId = signal<string>('manual');
  profileLoaded = signal(false);

  constructor(
    private matchingService: MatchingService,
    private profileService: ProfileService,
    private ingestionService: IngestionService,
  ) {}

  ngOnInit(): void {
    this.profileService.getCurrentProfile().subscribe({
      next: (profile) => {
        const summary = profile.sections
          .map(s => s.content)
          .join('\n\n')
          .substring(0, 2000);
        this.cvSummary.set(summary);
        this.cvSkills.set(profile.skills.join(', '));
        this.profileLoaded.set(true);
      },
      error: () => {},
    });

    this.ingestionService.listJobs().subscribe({
      next: (jobs) => this.jobs.set(jobs),
      error: () => {},
    });
  }

  onJobSelected(jobId: string): void {
    this.selectedJobId.set(jobId);
    if (jobId === 'manual') {
      this.jobDescription.set('');
      this.jobSkills.set('');
      return;
    }
    const job = this.jobs().find(j => j.id === jobId);
    if (job) {
      this.jobDescription.set(job.description);
      this.jobSkills.set(job.skills.join(', '));
    }
  }

  analyze(): void {
    this.loading.set(true);
    this.error.set('');
    const payload = {
      job_id: this.selectedJobId() !== 'manual' ? this.selectedJobId() : 'manual',
      cv_id: 'manual',
      job_description: this.jobDescription(),
      job_skills: this.jobSkills().split(',').map(s => s.trim()).filter(Boolean),
      cv_summary: this.cvSummary(),
      cv_skills: this.cvSkills().split(',').map(s => s.trim()).filter(Boolean),
    };
    this.matchingService.analyze(payload).subscribe({
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
    this.matchingService.evaluate(req).subscribe({
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
