import { ChangeDetectionStrategy, Component, computed, inject, input, output } from '@angular/core';
import { DatePipe } from '@angular/common';
import { Router, RouterLink } from '@angular/router';
import { NormalizedJob } from '@core/contracts/normalized-job.model';
import { parseJobDescription } from '../../lib/parse-job-description';
import { formatScorePercent } from '../../../../core/utils/format-score-percent';
import { scoreColor } from '../../../../core/utils/score-color';
import { JobDescriptionComponent } from '../job-description/job-description.component';
import { FeedbackControlsComponent } from '../feedback-controls/feedback-controls.component';
import { FeedbackKind } from '@core/contracts/feedback-kind.model';
import { CompanyLinkComponent } from '../../../../core/components/company-link';

@Component({
  selector: 'app-job-detail-panel',
  standalone: true,
  imports: [
    DatePipe,
    RouterLink,
    JobDescriptionComponent,
    FeedbackControlsComponent,
    CompanyLinkComponent,
  ],
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

  equityHighlight = computed(() => {
    const equity = this.job().equity_range?.trim();
    return equity || null;
  });

  alsoFoundOn = computed(() => {
    const meta = this.job().source_metadata;
    const raw = meta?.['also_found_on'];
    return Array.isArray(raw) ? raw : [];
  });

  // Open the direct application URL when the board gave us one — that hop
  // skips the aggregator's own apply page, which is where the walls live.
  applyUrl = computed(() => this.job().preferred_apply_url || this.job().url);

  // Non-null only when applying is walled, so the template can warn before the
  // user clicks through and hits a paywall or signup form.
  applyWarning = computed<{ label: string; note: string; paid: boolean } | null>(() => {
    const job = this.job();
    const access = job.apply_access;
    if (access !== 'paid_required' && access !== 'account_required') return null;
    const paid = access === 'paid_required';
    return {
      label: paid ? 'Paid subscription to apply' : 'Free account to apply',
      note: job.apply_access_note ?? '',
      paid,
    };
  });

  metaChips = computed(() => {
    const job = this.job();
    const chips: string[] = [];
    if (job.opportunity_type && job.opportunity_type !== 'unknown') {
      chips.push(this.opportunityTypeLabel(job.opportunity_type));
    } else if (job.employment_type) {
      chips.push(job.employment_type.replaceAll('_', ' '));
    }
    if (job.remote_modality) chips.push(job.remote_modality.replaceAll('_', ' '));
    if (job.international_pathways?.includes('visa_sponsorship')) {
      chips.push('visa sponsorship stated');
    }
    if (job.international_pathways?.includes('worldwide_remote')) {
      chips.push('worldwide remote');
    }
    if (job.requires_existing_work_authorization === true) {
      chips.push('existing work authorization required');
    }
    if (job.visa_sponsorship_available === false) {
      chips.push('no visa sponsorship stated');
    }
    const meta = job.source_metadata ?? {};
    for (const key of ['yc_batch', 'company_stage', 'employer_type', 'company_rating'] as const) {
      const value = meta[key];
      if (value !== undefined && value !== null && String(value).trim()) {
        chips.push(`${key.replaceAll('_', ' ')}: ${value}`);
      }
    }
    if (meta['easy_apply'] === true) chips.push('easy apply');
    return chips;
  });

  private opportunityTypeLabel(type: NonNullable<NormalizedJob['opportunity_type']>): string {
    const labels: Record<string, string> = {
      internship: 'Internship',
      entry_level: 'Entry-level / graduate',
      full_time: 'Full-time',
      part_time: 'Part-time',
      contract: 'Contract',
      temporary: 'Temporary',
      other: 'Other',
    };
    return labels[type] ?? type.replaceAll('_', ' ');
  }

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
}
