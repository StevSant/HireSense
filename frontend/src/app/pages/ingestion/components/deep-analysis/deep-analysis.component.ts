import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { JobAnalysis } from '../../models/job-analysis.model';
import { formatScorePercent } from '../../../../core/utils/format-score-percent';
import { scoreColor } from '../../../../core/utils/score-color';

@Component({
  selector: 'app-deep-analysis',
  standalone: true,
  imports: [],
  templateUrl: './deep-analysis.component.html',
  styleUrl: './deep-analysis.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DeepAnalysisComponent {
  analysis = input.required<JobAnalysis>();

  // Exposed for the template (shared single-source score utils).
  scoreColor = scoreColor;
  formatScorePercent = formatScorePercent;

  barWidth(score: number): string {
    const clamped = Math.max(0, Math.min(1, score));
    return `${Math.round(clamped * 100)}%`;
  }

  /** Turn a dimension key like "skills_role_fit" into "Skills role fit". */
  humanize(dimension: string): string {
    const spaced = dimension.replace(/_/g, ' ').trim();
    return spaced ? spaced.charAt(0).toUpperCase() + spaced.slice(1) : dimension;
  }
}
