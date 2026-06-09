import { ChangeDetectionStrategy, Component, DestroyRef, OnInit, computed, inject, signal } from '@angular/core';
import { DatePipe, Location } from '@angular/common';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { NormalizedJob } from '../ingestion/models/normalized-job.model';
import { JobAnalysis } from '../ingestion/models/job-analysis.model';
import { IngestionService } from '../../core/services/ingestion.service';
import { ApplicationsService } from '../../core/services/applications.service';
import { DeepAnalysisComponent } from '../ingestion/components/deep-analysis/deep-analysis.component';
import { MatchBreakdownComponent } from '../ingestion/components/match-breakdown/match-breakdown.component';
import { JobDescriptionComponent } from '../ingestion/components/job-description/job-description.component';
import { FeedbackControlsComponent } from '../ingestion/components/feedback-controls/feedback-controls.component';
import { formatScorePercent } from '../../core/utils/format-score-percent';
import { scoreColor } from '../../core/utils/score-color';

type Feature = 'matching' | 'optimization' | 'interview';

@Component({
  selector: 'app-job-detail',
  standalone: true,
  imports: [DatePipe, RouterLink, DeepAnalysisComponent, MatchBreakdownComponent, JobDescriptionComponent, FeedbackControlsComponent],
  templateUrl: './job.component.html',
  styleUrl: './job.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class JobDetailComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private location = inject(Location);
  private ingestion = inject(IngestionService);
  private applications = inject(ApplicationsService);
  private destroyRef = inject(DestroyRef);

  scoreColor = scoreColor;

  job = signal<NormalizedJob | null>(null);
  loading = signal(true);
  error = signal(false);

  analysis = signal<JobAnalysis | null>(null);
  analysisLoading = signal(false);
  analysisError = signal('');

  tracking = signal(false);
  trackError = signal('');

  // Prefer the Tier-2 deep-analysis score once it loads (the authoritative,
  // displayed value), falling back to the LLM quick-score and finally the
  // persisted heuristic blend that `getJob` returns. This keeps the header in
  // sync with the list's LLM score instead of showing the lower heuristic %.
  pillScore = computed<number | null>(() => {
    const j = this.job();
    if (!j) return null;
    return this.analysis()?.overall_score ?? j.llm_score ?? j.match_score;
  });
  scorePercent = computed(() => formatScorePercent(this.pillScore()));
  tracked = computed(() => {
    const j = this.job();
    return j ? this.ingestion.trackedJobIds().has(j.id) : false;
  });

  ngOnInit(): void {
    const id = this.route.snapshot.paramMap.get('id') ?? '';
    if (!id) {
      this.error.set(true);
      this.loading.set(false);
      return;
    }
    this.ingestion.getJob(id).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (j) => {
        this.job.set(j);
        this.loading.set(false);
        this.loadAnalysis(id);
      },
      error: () => {
        this.error.set(true);
        this.loading.set(false);
      },
    });
  }

  private loadAnalysis(id: string): void {
    const cached = this.ingestion.getCachedAnalysis(id);
    if (cached) {
      this.analysis.set(cached);
      return;
    }
    this.analysisLoading.set(true);
    this.analysisError.set('');
    this.ingestion.getJobAnalysis(id).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (a) => {
        this.analysis.set(a);
        this.analysisLoading.set(false);
      },
      error: (err) => {
        this.analysisError.set(err?.error?.detail || 'Deep analysis failed');
        this.analysisLoading.set(false);
      },
    });
  }

  retryAnalysis(): void {
    const j = this.job();
    if (j) this.loadAnalysis(j.id);
  }

  track(): void {
    const j = this.job();
    if (!j || this.tracked() || this.tracking()) return;
    this.tracking.set(true);
    this.trackError.set('');
    this.applications.createFromJob(j.id).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: () => {
        this.ingestion.markTracked(j.id);
        this.tracking.set(false);
      },
      error: (err) => {
        this.tracking.set(false);
        if (err?.status === 409) {
          this.ingestion.markTracked(j.id);   // already tracked
          return;
        }
        this.trackError.set(err?.error?.detail || 'Failed to track this job. Please try again.');
      },
    });
  }

  goTo(feature: Feature): void {
    const j = this.job();
    if (j) this.router.navigate([`/dashboard/${feature}`], { queryParams: { job_id: j.id } });
  }

  back(): void {
    this.location.back();
  }
}
