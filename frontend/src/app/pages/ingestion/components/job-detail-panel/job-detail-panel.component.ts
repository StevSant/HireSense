import { ChangeDetectionStrategy, Component, computed, inject, input, output } from '@angular/core';
import { DatePipe } from '@angular/common';
import { Router } from '@angular/router';
import { NormalizedJob } from '../../models/normalized-job.model';
import { parseJobDescription } from '../../lib/parse-job-description';
import { formatScorePercent } from '../../../../core/utils/format-score-percent';
import { scoreColor } from '../../../../core/utils/score-color';
import { JobDescriptionComponent } from '../job-description/job-description.component';
import { FeedbackControlsComponent } from '../feedback-controls/feedback-controls.component';
import { FeedbackKind } from '../../models/feedback-kind.model';

@Component({
  selector: 'app-job-detail-panel',
  standalone: true,
  imports: [DatePipe, JobDescriptionComponent, FeedbackControlsComponent],
  templateUrl: './job-detail-panel.component.html',
  styleUrl: './job-detail-panel.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class JobDetailPanelComponent {
  private router = inject(Router);

  job = input.required<NormalizedJob>();
  tracked = input<boolean>(false);
  tracking = input<boolean>(false);

  closed = output<void>();
  track = output<string>();
  feedbackSubmitted = output<FeedbackKind>();

  // Exposed for the template (shared single-source score util).
  scoreColor = scoreColor;

  // Match header: prefer the LLM quick score, fall back to the heuristic blend.
  pillScore = computed<number | null>(() => this.job().llm_score ?? this.job().match_score);
  scorePercent = computed(() => formatScorePercent(this.pillScore()));

  parsedDescription = computed(() => parseJobDescription(this.job().description ?? ''));

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
      this.closed.emit();
    }
  }

  /** Dismiss the panel with the Escape key for keyboard accessibility. */
  onEscape(): void {
    this.closed.emit();
  }

  onTrack(): void {
    this.track.emit(this.job().id);
  }

  goToMatching(): void {
    this.router.navigate(['/dashboard/matching'], { queryParams: { job_id: this.job().id } });
    this.closed.emit();
  }

  goToOptimization(): void {
    this.router.navigate(['/dashboard/optimization'], { queryParams: { job_id: this.job().id } });
    this.closed.emit();
  }

  goToInterview(): void {
    this.router.navigate(['/dashboard/interview'], { queryParams: { job_id: this.job().id } });
    this.closed.emit();
  }

  goToFullAnalysis(): void {
    this.router.navigate(['/dashboard/job', this.job().id]);
    this.closed.emit();
  }
}
