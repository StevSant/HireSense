import { ChangeDetectionStrategy, Component, OnInit, inject } from '@angular/core';
import { FunnelChartComponent } from '../../components/funnel-chart/funnel-chart.component';
import { PERCENT } from '../../analytics-row-caps';
import { AnalyticsStore } from '../../analytics.store';
import { StatusNoteComponent } from '@shared/ui';

/** Analytics -> Pipeline: the application funnel and outcomes by source. */
@Component({
  selector: 'app-analytics-pipeline-tab',
  standalone: true,
  imports: [FunnelChartComponent, StatusNoteComponent],
  templateUrl: './analytics-pipeline-tab.component.html',
  styleUrl: '../../analytics-tab-shared.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AnalyticsPipelineTabComponent implements OnInit {
  private store = inject(AnalyticsStore);

  funnel = this.store.funnel;
  funnelError = this.store.funnelError;

  ngOnInit(): void {
    // Idempotent: the shell already asked for this (funnel feeds a KPI tile),
    // but asking again keeps the tab self-sufficient when deep-linked.
    this.store.loadHeadline();
  }

  interviewPct(o: { interview_rate: number }): number {
    return Math.round(o.interview_rate * PERCENT);
  }
}
