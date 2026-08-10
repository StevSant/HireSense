import { ChangeDetectionStrategy, Component, OnInit, computed, inject } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { KpiStripComponent, KpiTile } from './components/kpi-strip/kpi-strip.component';
import { AnalyticsStore } from './analytics.store';
import { PERCENT } from './analytics-row-caps';
import { periodUnit, toPeriod } from '../../core/utils/pay-period';

/**
 * Analytics shell.
 *
 * The KPI strip stays above the routed tabs, so the tiles summarise every
 * section no matter which tab is open. That is why comp/funnel/focus are
 * fetched eagerly here rather than deferred to their tabs — the tiles need all
 * three immediately. Market, skill gap and engagement load with their tab.
 */
@Component({
  selector: 'app-analytics',
  standalone: true,
  imports: [RouterOutlet, KpiStripComponent],
  templateUrl: './analytics.component.html',
  styleUrl: './analytics.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AnalyticsComponent implements OnInit {
  private store = inject(AnalyticsStore);

  ngOnInit(): void {
    this.store.loadHeadline();
  }

  // Headline KPIs, composed from the section payloads. Each degrades to "—".
  kpis = computed<KpiTile[]>(() => {
    const c = this.store.comp();
    const f = this.store.funnel();
    const focus = this.store.focus();
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
          ? `${c!.currency ?? ''} ${toPeriod(c!.median_annual, this.store.payPeriod())!.toLocaleString('en-US')} ${periodUnit(this.store.payPeriod())}`.trim()
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
}
