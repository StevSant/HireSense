import { ChangeDetectionStrategy, Component, OnInit, inject } from '@angular/core';
import { BarChartComponent } from '../../components/bar-chart/bar-chart.component';
import { SearchFocusComponent } from '../../components/search-focus/search-focus.component';
import { SkillGap } from '../../models/skill-gap.model';
import { BarRow } from '../../models/bar-row.model';
import { MARKET_ROW_CAP } from '../../analytics-row-caps';
import { AnalyticsStore } from '../../analytics.store';

/** Analytics -> Fit: where the profile lands, and what it is missing. */
@Component({
  selector: 'app-analytics-fit-tab',
  standalone: true,
  imports: [BarChartComponent, SearchFocusComponent],
  templateUrl: './analytics-fit-tab.component.html',
  styleUrl: '../../analytics-tab-shared.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AnalyticsFitTabComponent implements OnInit {
  private store = inject(AnalyticsStore);

  focus = this.store.focus;
  focusError = this.store.focusError;
  skillGap = this.store.skillGap;
  skillGapError = this.store.skillGapError;

  ngOnInit(): void {
    this.store.loadHeadline();
    this.store.loadSkillGap();
  }

  gapRows(g: SkillGap): BarRow[] {
    return g.missing
      .slice(0, MARKET_ROW_CAP)
      .map((s) => ({ label: s.skill, value: s.count, pct: s.pct, note: `in ${s.pct}%` }));
  }

  gapTruncated(g: SkillGap): number {
    return Math.max(0, g.missing.length - MARKET_ROW_CAP);
  }
}
