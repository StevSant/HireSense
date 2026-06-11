import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { JobAnalysis } from '../../models/job-analysis.model';

/** Qualitative half of the deep analysis: narrative, pros/cons, and
 *  recommendations. The quantitative scorecard (overall score, verdict,
 *  dimension bars, matched/gap skills) is rendered separately in the job
 *  page rail. */
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
}
