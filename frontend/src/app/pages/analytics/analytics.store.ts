import { DestroyRef, Injectable, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { AnalyticsService } from '../../core/services/analytics.service';
import { PortfolioService } from '../../core/services/portfolio.service';
import { PayPeriod } from '../../core/utils/pay-period';
import { CompBenchmark } from './models/comp-benchmark.model';
import { FunnelMetrics } from './models/funnel-metrics.model';
import { MarketIntel } from './models/market-intel.model';
import { SearchFocus } from './models/search-focus.model';
import { SkillGap } from './models/skill-gap.model';
import { PortfolioEngagementResponse } from '../profile/models/portfolio-engagement.model';

/**
 * Shared state for the Analytics hub.
 *
 * Provided on the analytics route, so the shell and every tab see one instance
 * that is discarded when the user leaves (matching the previous single-page
 * behaviour — no stale data on a later visit).
 *
 * The split matters: `loadHeadline()` runs eagerly in the shell because comp,
 * funnel and focus feed the KPI strip that sits above the tabs. Market, skill
 * gap and engagement are only fetched when their tab is first opened. Every
 * loader is idempotent, so switching tabs back and forth refetches nothing.
 */
@Injectable()
export class AnalyticsStore {
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

  /** Shared by the KPI strip and the Pay tab's period toggle. */
  payPeriod = signal<PayPeriod>('annual');

  private headlineRequested = false;
  private marketRequested = false;
  private skillGapRequested = false;
  private engagementRequested = false;

  setPayPeriod(p: PayPeriod): void {
    this.payPeriod.set(p);
  }

  /** comp + funnel + focus — the KPI tiles need all three regardless of tab. */
  loadHeadline(): void {
    if (this.headlineRequested) return;
    this.headlineRequested = true;
    this.analytics
      .funnel()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (v) => this.funnel.set(v),
        error: () => this.funnelError.set(true),
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
  }

  loadMarket(): void {
    if (this.marketRequested) return;
    this.marketRequested = true;
    this.analytics
      .market()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (v) => this.market.set(v),
        error: () => this.marketError.set(true),
      });
  }

  loadSkillGap(): void {
    if (this.skillGapRequested) return;
    this.skillGapRequested = true;
    this.analytics
      .skillGap()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (v) => this.skillGap.set(v),
        error: () => this.skillGapError.set(true),
      });
  }

  loadEngagement(): void {
    if (this.engagementRequested) return;
    this.engagementRequested = true;
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
}
