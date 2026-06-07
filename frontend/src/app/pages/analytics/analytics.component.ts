import { ChangeDetectionStrategy, Component, DestroyRef, inject, OnInit, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { AnalyticsService } from '../../core/services/analytics.service';
import { FunnelMetrics } from './models/funnel-metrics.model';
import { MarketIntel } from './models/market-intel.model';
import { SkillGap } from './models/skill-gap.model';
import { TargetSalary } from './models/target-salary.model';
import { BarRow } from './models/bar-row.model';
import { BarChartComponent } from './components/bar-chart/bar-chart.component';
import { FunnelChartComponent } from './components/funnel-chart/funnel-chart.component';
import { TrendLineComponent } from './components/trend-line/trend-line.component';
import { SalaryBandComponent } from './components/salary-band/salary-band.component';

@Component({
  selector: 'app-analytics',
  standalone: true,
  imports: [BarChartComponent, FunnelChartComponent, TrendLineComponent, SalaryBandComponent],
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

  targetSalary = signal<TargetSalary | null>(null);
  targetSalaryError = signal(false);

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
    this.analytics.targetSalary().pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (v) => this.targetSalary.set(v), error: () => this.targetSalaryError.set(true),
    });
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
      label: k, value: v, pct: Math.round((v / total) * 100), note: `${Math.round((v / total) * 100)}%`,
    }));
  }

  fmt(v: number | null): string {
    return v === null ? '—' : v.toLocaleString('en-US');
  }
}
