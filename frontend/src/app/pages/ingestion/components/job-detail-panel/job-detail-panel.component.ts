import { ChangeDetectionStrategy, Component, computed, inject, input, output, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { Router } from '@angular/router';
import { NormalizedJob } from '../../models/normalized-job.model';
import { JobAnalysis } from '../../models/job-analysis.model';
import { parseJobDescription } from '../../lib/parse-job-description';
import { IngestionService } from '../../../../core/services/ingestion.service';
import { formatScorePercent } from '../../../../core/utils/format-score-percent';
import { scoreColor } from '../../../../core/utils/score-color';
import { DeepAnalysisComponent } from '../deep-analysis/deep-analysis.component';

@Component({
  selector: 'app-job-detail-panel',
  standalone: true,
  imports: [DatePipe, DeepAnalysisComponent],
  templateUrl: './job-detail-panel.component.html',
  styleUrl: './job-detail-panel.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class JobDetailPanelComponent {
  private router = inject(Router);
  private ingestionService = inject(IngestionService);

  job = input.required<NormalizedJob>();
  tracked = input<boolean>(false);

  close = output<void>();
  track = output<string>();

  // Exposed for the template (shared single-source score util).
  scoreColor = scoreColor;

  // Match header: prefer the LLM quick score, fall back to the heuristic blend.
  pillScore = computed<number | null>(() => this.job().llm_score ?? this.job().match_score);
  scorePercent = computed(() => formatScorePercent(this.pillScore()));

  // Deep analysis (lazy, advanced model). The result is cached in the service
  // (keyed by job id) so it survives the panel being destroyed on close.
  analysis = computed<JobAnalysis | null>(
    () => this.ingestionService.getCachedAnalysis(this.job().id) ?? null,
  );
  analysisExpanded = signal(false);
  analysisLoading = signal(false);
  analysisError = signal('');

  parsedDescription = computed(() => parseJobDescription(this.job().description ?? ''));

  hasStructuredSections = computed(() => this.parsedDescription().sections.length > 0);

  /** Pull out the most prominent compensation line for the header strip. */
  compensationHighlight = computed(() => {
    const job = this.job();
    if (job.salary_range && job.salary_range.trim()) return job.salary_range.trim();
    const compSection = this.parsedDescription().sections.find(
      (s) => s.emphasis === 'compensation',
    );
    if (!compSection) return null;
    const firstLine = compSection.body
      .split('\n')
      .map((l) => l.trim())
      .find((l) => l.length > 0);
    return firstLine ?? null;
  });

  onOverlayClick(event: MouseEvent): void {
    if ((event.target as HTMLElement).classList.contains('panel-overlay')) {
      this.close.emit();
    }
  }

  onTrack(): void {
    this.track.emit(this.job().id);
  }

  toggleDeepAnalysis(): void {
    const next = !this.analysisExpanded();
    this.analysisExpanded.set(next);
    if (next && this.analysis() === null && !this.analysisLoading()) {
      this.loadAnalysis();
    }
  }

  loadAnalysis(force = false): void {
    this.analysisLoading.set(true);
    this.analysisError.set('');
    this.ingestionService.getJobAnalysis(this.job().id, force).subscribe({
      next: () => this.analysisLoading.set(false),
      error: (err) => {
        this.analysisError.set(err.error?.detail || 'Deep analysis failed');
        this.analysisLoading.set(false);
      },
    });
  }

  retryAnalysis(): void {
    this.loadAnalysis();
  }

  goToMatching(): void {
    this.router.navigate(['/dashboard/matching'], { queryParams: { job_id: this.job().id } });
    this.close.emit();
  }

  goToOptimization(): void {
    this.router.navigate(['/dashboard/optimization'], { queryParams: { job_id: this.job().id } });
    this.close.emit();
  }

  goToInterview(): void {
    this.router.navigate(['/dashboard/interview'], { queryParams: { job_id: this.job().id } });
    this.close.emit();
  }
}
