import { ChangeDetectionStrategy, Component, DestroyRef, computed, inject, OnInit, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { AnalyticsService } from '../../core/services/analytics.service';
import { FunnelMetrics } from './models/funnel-metrics.model';
import { MarketIntel } from './models/market-intel.model';
import { SkillGap } from './models/skill-gap.model';
import { CompBenchmark } from './models/comp-benchmark.model';
import { SearchFocus } from './models/search-focus.model';
import { BarRow } from './models/bar-row.model';
import { BarChartComponent } from './components/bar-chart/bar-chart.component';
import { FunnelChartComponent } from './components/funnel-chart/funnel-chart.component';
import { TrendLineComponent } from './components/trend-line/trend-line.component';
import { CompBenchmarkComponent } from './components/comp-benchmark/comp-benchmark.component';
import { SearchFocusComponent } from './components/search-focus/search-focus.component';
import { KpiStripComponent, KpiTile } from './components/kpi-strip/kpi-strip.component';

const PERCENT = 100;

@Component({
  selector: 'app-analytics',
  standalone: true,
  imports: [
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

  ngOnInit(): void {
    this.analytics.funnel().pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (v) => this.funnel.set(v), error: () => this.funnelError.set(true),
    });
    this.analytics.market().pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (v) => this.market.set(v), error: () => this.marketError.set(true),
    });
    this.analytics.skillGap().pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (v) => this.skillGap.set(v), error: () => this.skillGapError.set(true),
    });
    this.analytics.comp().pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (v) => this.comp.set(v), error: () => this.compError.set(true),
    });
    this.analytics.focus().pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (v) => this.focus.set(v), error: () => this.focusError.set(true),
    });
  }

  // Headline KPIs, composed from the section payloads. Each degrades to "—".
  kpis = computed<KpiTile[]>(() => {
    const c = this.comp();
    const f = this.funnel();
    const focus = this.focus();
    const applyToInterview = f
      ? f.stages.find((s) => s.stage === 'interviewing')?.conversion_from_prev ?? null
      : null;
    return [
      {
        label: 'Target median',
        value: c && !c.insufficient_data && c.median_annual !== null
          ? `${c.currency ?? ''} ${c.median_annual.toLocaleString('en-US')}`.trim()
          : '—',
        hint: 'for your profile',
      },
      {
        label: 'Apply → interview',
        value: applyToInterview === null ? '—' : `${Math.round(applyToInterview * PERCENT)}%`,
        hint: f ? `${f.total_applications} tracked` : undefined,
      },
      {
        label: 'Fresh-fit jobs',
        value: focus && !focus.insufficient_data ? `${focus.fresh_fit_count}` : '—',
        hint: 'matched, recent',
      },
      {
        label: 'Best-fit companies',
        value: focus && !focus.insufficient_data ? `${focus.best_fit_companies.length}` : '—',
        hint: focus && !focus.insufficient_data ? `${focus.match_count} matches` : undefined,
      },
    ];
  });

  sourceRows(f: FunnelMetrics): BarRow[] {
    return f.by_source.map((o) => ({
      label: o.source,
      value: o.applications,
      pct: Math.round(o.interview_rate * PERCENT),
      note: `${o.reached_interview}/${o.applications} → interview`,
    }));
  }

  skillRows(m: MarketIntel): BarRow[] {
    return m.top_skills.map((s) => ({ label: s.skill, value: s.count, pct: s.pct, note: `${s.pct}%` }));
  }

  gapRows(g: SkillGap): BarRow[] {
    return g.missing.map((s) => ({ label: s.skill, value: s.count, pct: s.pct, note: `in ${s.pct}%` }));
  }

  remoteRows(m: MarketIntel): BarRow[] {
    const total = Object.values(m.remote_mix).reduce((a, b) => a + b, 0) || 1;
    return Object.entries(m.remote_mix).map(([k, v]) => ({
      label: k, value: v, pct: Math.round((v / total) * PERCENT), note: `${Math.round((v / total) * PERCENT)}%`,
    }));
  }

  fmt(v: number | null): string {
    return v === null ? '—' : v.toLocaleString('en-US');
  }
}
