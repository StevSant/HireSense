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
import { dimensionLabel as toDimensionLabel } from '../../core/utils/dimension-label';
import { mapLlmError } from '../../core/services/llm-error.util';
import { LlmRunnerService } from '../../core/services/llm-runner.service';

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
  private llmRunner = inject(LlmRunnerService);
  private route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);

  jobDescription = signal('');
  jobSkills = signal('');
  cvSummary = signal('');
  cvSkills = signal('');

  // Keyed by the selected job id (or 'manual') + operation, so analyze and
  // evaluate runs for different jobs never clash. Both live in
  // LlmRunnerService so they survive navigating away from this page.
  private analyzeKey = computed(() => `matching:analyze:${this.selectedJobId()}`);
  private evaluateKey = computed(() => `matching:evaluate:${this.selectedJobId()}`);

  result = computed(() => this.llmRunner.result<MatchResult>(this.analyzeKey()));
  loading = computed(() => this.llmRunner.isRunning(this.analyzeKey()));
  evaluationResult = computed(() => this.llmRunner.result<EvaluationResult>(this.evaluateKey()));
  evaluating = computed(() => this.llmRunner.isRunning(this.evaluateKey()));
  error = computed(
    () => this.llmRunner.error(this.analyzeKey()) || this.llmRunner.error(this.evaluateKey()),
  );

  jobs = signal<NormalizedJob[]>([]);
  selectedJobId = signal<string>('manual');
  profileLoaded = signal(false);
  // Gates the dropdown's job list fetch so it only fires once, the first
  // time the select is opened, instead of eagerly on every page load.
  private jobsRequested = signal(false);

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
      this.profileService
        .listProfiles()
        .pipe(takeUntilDestroyed(this.destroyRef))
        .subscribe({
          next: () => this.applyProfile(),
          error: () => {
            this.profileService
              .getCurrentProfile()
              .pipe(takeUntilDestroyed(this.destroyRef))
              .subscribe({
                next: () => this.applyProfile(),
                error: () => {},
              });
          },
        });
    } else {
      this.applyProfile();
    }

    // The dropdown's job list is now loaded lazily (see ensureJobsLoaded()),
    // not eagerly here — this only resolves the ?job_id= deep-link, which
    // works standalone via the single-job fallback fetch below regardless of
    // whether the dropdown has been opened yet.
    this.applyJobIdFromQuery();
  }

  /**
   * Lazily loads the dropdown's job list the first time the select is
   * opened, instead of eagerly on every page load. A small page (25, not
   * 100) is enough to populate the dropdown; picking an older job is still
   * possible via manual entry or a job's own "Analyze match" link.
   */
  ensureJobsLoaded(): void {
    if (this.jobsRequested()) return;
    this.jobsRequested.set(true);
    this.ingestionService
      .queryJobs('boards', 1, 25)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          // Preserve a deep-linked job the fallback fetch already prepended
          // (see applyJobIdFromQuery) if it didn't also come back in this page.
          const deepLinked = this.jobs().find(
            (j) => j.id === this.selectedJobId() && !res.jobs.some((r) => r.id === j.id),
          );
          this.jobs.set(deepLinked ? [deepLinked, ...res.jobs] : res.jobs);
        },
        error: () => {
          // Allow retry on the next open rather than getting stuck empty.
          this.jobsRequested.set(false);
        },
      });
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
    // Not in the (possibly not-yet-loaded) dropdown list — fetch directly.
    this.ingestionService
      .getJob(jobId)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
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
      .map((s) => s.content)
      .join('\n\n')
      .substring(0, 2000);
    this.cvSummary.set(summary);
    this.cvSkills.set(profile.skills.join(', '));
    this.profileLoaded.set(true);
  }

  toggleSkill(skill: string): void {
    const current = this.cvSkills()
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);
    const lower = skill.toLowerCase();
    const idx = current.findIndex((s) => s.toLowerCase() === lower);
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
      .map((s) => s.trim().toLowerCase())
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
    const job = this.jobs().find((j) => j.id === jobId);
    if (job) {
      this.jobDescription.set(job.description);
      this.jobSkills.set(job.skills.join(', '));
    }
  }

  analyze(): void {
    const payload = {
      job_id: this.selectedJobId() !== 'manual' ? this.selectedJobId() : 'manual',
      cv_id: 'manual',
      job_description: this.jobDescription(),
      job_skills: this.jobSkills()
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean),
      cv_summary: this.cvSummary(),
      cv_skills: this.cvSkills()
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean),
    };
    this.llmRunner.run(this.analyzeKey(), this.matchingService.analyze(payload), (err) =>
      mapLlmError(err, 'Analysis failed'),
    );
  }

  evaluate(): void {
    const req: EvaluateRequest = {
      job_title: this.jobDescription().split('\n')[0] || 'Unknown',
      company: 'Unknown',
      description: this.jobDescription(),
      skills: this.jobSkills()
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean),
    };
    this.llmRunner.run(this.evaluateKey(), this.matchingService.evaluate(req), (err) =>
      mapLlmError(err, 'Evaluation failed'),
    );
  }

  /** Clears both cached runs for the current job so the form reappears. */
  startNewAnalysis(): void {
    this.llmRunner.clear(this.analyzeKey());
    this.llmRunner.clear(this.evaluateKey());
  }

  dimensionLabel(dimension: string): string {
    return toDimensionLabel(dimension);
  }

  scoreColor(score: number): string {
    return toScoreColor(score);
  }

  scorePercent(score: number): string {
    return formatScorePercent(score, false);
  }
}
