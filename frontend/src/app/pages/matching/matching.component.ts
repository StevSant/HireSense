import { Component, DestroyRef, computed, inject, OnInit, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { MatchingService } from '../../core/services/matching.service';
import { ProfileService } from '../../core/services/profile.service';
import { IngestionService } from '../../core/services/ingestion.service';
import { NormalizedJob } from '../ingestion/models/normalized-job.model';
import { EvaluateRequest } from './models/evaluate-request.model';
import { EvaluationResult } from './models/evaluation-result.model';
import { MatchResult } from './models/match-result.model';
import { scoreColor as toScoreColor } from '../../core/utils/score-color';
import { formatScorePercent } from '../../core/utils/format-score-percent';

@Component({
  selector: 'app-matching',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './matching.component.html',
  styleUrl: './matching.component.scss',
})
export class MatchingComponent implements OnInit {
  private matchingService = inject(MatchingService);
  private profileService = inject(ProfileService);
  private ingestionService = inject(IngestionService);
  private route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);

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

  /** Available CV languages from uploaded profiles */
  availableLanguages = computed(() => Object.keys(this.profileService.profiles()));
  selectedCvLanguage = signal('en');

  /** Profile skills as array for chip display */
  profileSkills = computed(() => {
    const profiles = this.profileService.profiles();
    const lang = this.selectedCvLanguage();
    const profile = profiles[lang] ?? Object.values(profiles)[0];
    return profile?.skills ?? [];
  });

  constructor() {}

  ngOnInit(): void {
    // Load profiles if not cached
    if (this.availableLanguages().length === 0) {
      this.profileService.listProfiles().pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
        next: () => this.applyProfile(),
        error: () => {
          this.profileService.getCurrentProfile().pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
            next: () => this.applyProfile(),
            error: () => {},
          });
        },
      });
    } else {
      this.applyProfile();
    }

    // If no jobs in cache, try fetching from server
    if (this.jobs().length === 0) {
      this.ingestionService.queryJobs('boards', 1, 100).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
        next: (res) => {
          this.jobs.set(res.jobs);
          this.applyJobIdFromQuery();
        },
        error: () => {},
      });
    } else {
      this.applyJobIdFromQuery();
    }
  }

  private applyJobIdFromQuery(): void {
    const jobId = this.route.snapshot.queryParamMap.get('job_id');
    if (!jobId) return;
    const job = this.jobs().find((j) => j.id === jobId);
    if (job) {
      this.selectedJobId.set(jobId);
      this.jobDescription.set(job.description);
      this.jobSkills.set(job.skills.join(', '));
      return;
    }
    // Job not in the first 100 — fetch directly
    this.ingestionService.getJob(jobId).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (j) => {
        this.jobs.update((list) => [j, ...list]);
        this.selectedJobId.set(jobId);
        this.jobDescription.set(j.description);
        this.jobSkills.set(j.skills.join(', '));
      },
      error: () => {},
    });
  }

  onCvLanguageChange(lang: string): void {
    this.selectedCvLanguage.set(lang);
    this.applyProfile();
  }

  private applyProfile(): void {
    const profiles = this.profileService.profiles();
    const lang = this.selectedCvLanguage();
    const profile = profiles[lang] ?? Object.values(profiles)[0];
    if (!profile) return;

    // Update selected language to match what we actually found
    this.selectedCvLanguage.set(profile.language);

    const summary = profile.sections
      .map(s => s.content)
      .join('\n\n')
      .substring(0, 2000);
    this.cvSummary.set(summary);
    this.cvSkills.set(profile.skills.join(', '));
    this.profileLoaded.set(true);
  }

  toggleSkill(skill: string): void {
    const current = this.cvSkills()
      .split(',')
      .map(s => s.trim())
      .filter(Boolean);
    const lower = skill.toLowerCase();
    const idx = current.findIndex(s => s.toLowerCase() === lower);
    if (idx >= 0) {
      current.splice(idx, 1);
    } else {
      current.push(skill);
    }
    this.cvSkills.set(current.join(', '));
  }

  isSkillSelected(skill: string): boolean {
    const current = this.cvSkills()
      .split(',')
      .map(s => s.trim().toLowerCase())
      .filter(Boolean);
    return current.includes(skill.toLowerCase());
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
    this.matchingService.analyze(payload).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
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
    this.matchingService.evaluate(req).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
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
    return toScoreColor(score);
  }

  scorePercent(score: number): string {
    return formatScorePercent(score, false);
  }
}
