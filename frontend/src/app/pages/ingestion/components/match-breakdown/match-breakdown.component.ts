import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { AnalysisDimension } from '../../models/analysis-dimension.model';
import { formatScorePercent } from '../../../../core/utils/format-score-percent';
import { scoreColor } from '../../../../core/utils/score-color';

/** Compact per-dimension score bars for the job scorecard rail. Each row with a
 *  rationale expands it on click; bars stay scannable by default. */
@Component({
  selector: 'app-match-breakdown',
  standalone: true,
  imports: [],
  templateUrl: './match-breakdown.component.html',
  styleUrl: './match-breakdown.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class MatchBreakdownComponent {
  dimensions = input.required<AnalysisDimension[]>();

  scoreColor = scoreColor;
  formatScorePercent = formatScorePercent;

  barWidth(score: number): string {
    const clamped = Math.max(0, Math.min(1, score));
    return `${Math.round(clamped * 100)}%`;
  }

  humanize(dimension: string): string {
    const spaced = dimension.replace(/_/g, ' ').trim();
    return spaced ? spaced.charAt(0).toUpperCase() + spaced.slice(1) : dimension;
  }
}
