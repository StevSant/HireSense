import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  computed,
  inject,
  OnInit,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { DatePipe } from '@angular/common';
import { AnalyticsService } from '../../core/services/analytics.service';
import { PortfolioService } from '../../core/services/portfolio.service';
import { FunnelMetrics } from './models/funnel-metrics.model';
import { MarketIntel } from './models/market-intel.model';
import { SkillGap } from './models/skill-gap.model';
import { CompBenchmark } from './models/comp-benchmark.model';
import { SearchFocus } from './models/search-focus.model';
import { BarRow } from './models/bar-row.model';
import {
  PortfolioEngagementResponse,
  PortfolioVisit,
} from '../profile/models/portfolio-engagement.model';
import { BarChartComponent } from './components/bar-chart/bar-chart.component';
import { FunnelChartComponent } from './components/funnel-chart/funnel-chart.component';
import { TrendLineComponent } from './components/trend-line/trend-line.component';
import { CompBenchmarkComponent } from './components/comp-benchmark/comp-benchmark.component';
import { SearchFocusComponent } from './components/search-focus/search-focus.component';
import { KpiStripComponent, KpiTile } from './components/kpi-strip/kpi-strip.component';

const PERCENT = 100;

const ENGAGEMENT_ROW_CAP = 10;

@Component({
  selector: 'app-analytics',
  standalone: true,
  imports: [
    DatePipe,
    BarChartComponent,
    FunnelChartComponent,
    TrendLineComponent,
    CompBenchmarkComponent,
    SearchFocusComponent,
    KpiStripComponent,
  ],
  templateUrl: './analytics.component.html',
  styleUrl: './analytics.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AnalyticsComponent implements OnInit {
  private analytics = inject(AnalyticsService);
  private portfolioService = inject(PortfolioService);
  private destroyRef = inject(DestroyRef);

  funnel = signal<FunnelMetrics | null>(null);
  funnelError = signal(false);

  market = signal<MarketIntel | null>(null);
  marketError = signal(false);

  skillGap = signal<SkillGap | null>(null);
  skillGapError = signal(false);

  comp = signal<CompBenchmark | null>(null);
  compError = signal(false);

  focus = signal<SearchFocus | null>(null);
  focusError = signal(false);

  engagement = signal<PortfolioEngagementResponse | null>(null);

  ngOnInit(): void {
    this.analytics
      .funnel()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (v) => this.funnel.set(v),
        error: () => this.funnelError.set(true),
      });
    this.analytics
      .market()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (v) => this.market.set(v),
        error: () => this.marketError.set(true),
      });
    this.analytics
      .skillGap()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (v) => this.skillGap.set(v),
        error: () => this.skillGapError.set(true),
      });
    this.analytics
      .comp()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (v) => this.comp.set(v),
        error: () => this.compError.set(true),
      });
    this.analytics
      .focus()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (v) => this.focus.set(v),
        error: () => this.focusError.set(true),
      });
    this.portfolioService
      .engagement()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (v) => this.engagement.set(v),
        error: () => {
          /* keep empty on error */
        },
      });
  }

  // Headline KPIs, composed from the section payloads. Each degrades to "—".
  kpis = computed<KpiTile[]>(() => {
    const c = this.comp();
    const f = this.funnel();
    const focus = this.focus();
    const compReady = c !== null && !c.insufficient_data && c.median_annual !== null;
    const focusReady = focus !== null && !focus.insufficient_data;
    const applyToInterview = f
      ? (f.stages.find((s) => s.stage === 'interviewing')?.conversion_from_prev ?? null)
      : null;
    const applied = f?.stages.find((s) => s.stage === 'applied')?.reached ?? null;
    const interviewing = f?.stages.find((s) => s.stage === 'interviewing')?.reached ?? null;
    return [
      {
        label: 'Target median',
        value: compReady
          ? `${c!.currency ?? ''} ${c!.median_annual!.toLocaleString('en-US')}`.trim()
          : '—',
        hint: compReady ? `across ${c!.sample_size} matched roles` : 'for your profile',
      },
      {
        label: 'Apply → interview',
        value: applyToInterview === null ? '—' : `${Math.round(applyToInterview * PERCENT)}%`,
        hint:
          applied !== null && applied > 0
            ? `${interviewing ?? 0} of ${applied} reached interview`
            : f
              ? `${f.total_applications} tracked`
              : undefined,
      },
      {
        label: 'Fresh-fit jobs',
        value: focusReady ? `${focus!.fresh_fit_count}` : '—',
        hint: focusReady ? `new in the last ${focus!.fresh_days} days` : 'matched, recent',
      },
      {
        label: 'Best-fit companies',
        value: focusReady ? `${focus!.best_fit_companies.length}` : '—',
        hint: focusReady ? `${focus!.match_count} matches` : undefined,
      },
    ];
  });

  // Cap the secondary market/skill-gap lists so they don't become 20-row walls.
  private static readonly MARKET_ROW_CAP = 8;

  interviewPct(o: { interview_rate: number }): number {
    return Math.round(o.interview_rate * PERCENT);
  }

  skillRows(m: MarketIntel): BarRow[] {
    return m.top_skills
      .slice(0, AnalyticsComponent.MARKET_ROW_CAP)
      .map((s) => ({ label: s.skill, value: s.count, pct: s.pct, note: `${s.pct}%` }));
  }

  gapRows(g: SkillGap): BarRow[] {
    return g.missing
      .slice(0, AnalyticsComponent.MARKET_ROW_CAP)
      .map((s) => ({ label: s.skill, value: s.count, pct: s.pct, note: `in ${s.pct}%` }));
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

  fmt(v: number | null): string {
    return v === null ? '—' : v.toLocaleString('en-US');
  }

  engagementRows(e: PortfolioEngagementResponse): PortfolioVisit[] {
    return e.visits.slice(0, ENGAGEMENT_ROW_CAP);
  }

  visitLabel(visit: PortfolioVisit): string {
    return visit.application_id ?? visit.ref;
  }
}
