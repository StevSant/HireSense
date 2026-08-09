import { ChangeDetectionStrategy, Component, OnInit, inject } from '@angular/core';
import { BarChartComponent } from '../../components/bar-chart/bar-chart.component';
import { TrendLineComponent } from '../../components/trend-line/trend-line.component';
import { MarketIntel } from '../../models/market-intel.model';
import { BarRow } from '../../models/bar-row.model';
import { MARKET_ROW_CAP, PERCENT } from '../../analytics-row-caps';
import { AnalyticsStore } from '../../analytics.store';

/** Analytics -> Market: what the corpus as a whole looks like. */
@Component({
  selector: 'app-analytics-market-tab',
  standalone: true,
  imports: [BarChartComponent, TrendLineComponent],
  templateUrl: './analytics-market-tab.component.html',
  styleUrl: '../../analytics-tab-shared.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AnalyticsMarketTabComponent implements OnInit {
  private store = inject(AnalyticsStore);

  market = this.store.market;
  marketError = this.store.marketError;

  ngOnInit(): void {
    this.store.loadMarket();
  }

  skillRows(m: MarketIntel): BarRow[] {
    return m.top_skills
      .slice(0, MARKET_ROW_CAP)
      .map((s) => ({ label: s.skill, value: s.count, pct: s.pct, note: `${s.pct}%` }));
  }

  remoteRows(m: MarketIntel): BarRow[] {
    const total = Object.values(m.remote_mix).reduce((a, b) => a + b, 0) || 1;
    return Object.entries(m.remote_mix).map(([k, v]) => ({
      label: k,
      value: v,
      pct: Math.round((v / total) * PERCENT),
      note: `${Math.round((v / total) * PERCENT)}%`,
    }));
  }

  skillsTruncated(m: MarketIntel): number {
    return Math.max(0, m.top_skills.length - MARKET_ROW_CAP);
  }
}
