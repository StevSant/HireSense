import { DestroyRef, Injectable, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { HttpErrorResponse } from '@angular/common/http';
import { AdminUsageService } from '@core/services/admin-usage.service';
import { BreakdownResponse } from '@core/contracts/breakdown-response.model';
import { DashboardSummary } from '@core/contracts/dashboard-summary.model';
import { RecentCallsResponse } from '@core/contracts/recent-calls-response.model';
import { TimeseriesResponse } from '@core/contracts/timeseries-response.model';
import { UsageBucket } from '@core/contracts/usage-bucket.model';
import { createSortState } from '@core/utils/sort-state';
import { sortItems } from '@core/utils/sort-items';

export type Dimension = 'provider' | 'model' | 'feature';
export type BreakdownSortField = 'key' | 'calls' | 'total_tokens' | 'cost_usd';
export type CallsSortField = 'created' | 'cost' | 'latency' | 'input_tokens' | 'output_tokens';

/**
 * State and orchestration for the admin LLM usage dashboard.
 *
 * Provided by AdminUsageComponent, so the four panels share one instance that
 * is discarded on leave.
 *
 * Two concerns live here: the aggregate panels (summary, timeseries,
 * breakdown) whose reloads are driven by the range and dimension toggles, and
 * the server-paginated recent-calls table with its filter/sort/page state.
 * They share a store because they share `loading`/`error` and one range.
 */
@Injectable()
export class AdminUsageStore {
  private api = inject(AdminUsageService);
  private readonly destroyRef = inject(DestroyRef);

  loading = signal(false);
  error = signal('');

  summary = signal<DashboardSummary | null>(null);
  timeseries = signal<TimeseriesResponse | null>(null);
  breakdown = signal<BreakdownResponse | null>(null);
  recent = signal<RecentCallsResponse | null>(null);

  rangeDays = signal<number>(30);
  dimension = signal<Dimension>('feature');

  // Recent-calls filters
  filterProvider = signal('');
  filterModel = signal('');
  filterFeature = signal('');
  recentLimit = signal(50);

  // Derived: max cost in timeseries for SVG scaling
  maxBucketCost = computed(() => {
    const buckets = this.timeseries()?.buckets ?? [];
    return Math.max(0.0001, ...buckets.map((b) => b.cost_usd));
  });

  maxBreakdownCost = computed(() => {
    const buckets = this.breakdown()?.buckets ?? [];
    return Math.max(0.0001, ...buckets.map((b) => b.cost_usd));
  });

  // Breakdown is sorted client-side over the already-aggregated buckets.
  breakdownSort = createSortState<BreakdownSortField>('cost_usd', 'desc', ['key']);
  visibleBuckets = computed(() => {
    const buckets = this.breakdown()?.buckets ?? [];
    const field = this.breakdownSort.field();
    return sortItems(buckets, (b) => this.bucketValue(b, field), this.breakdownSort.dir());
  });

  private bucketValue(b: UsageBucket, field: BreakdownSortField): string | number {
    switch (field) {
      case 'key':
        return b.key;
      case 'calls':
        return b.calls;
      case 'total_tokens':
        return b.total_tokens;
      case 'cost_usd':
        return b.cost_usd;
    }
  }

  // Recent calls are server-paginated (limit/offset), so sorting and paging
  // both re-query rather than reordering a local slice.
  callsSort = createSortState<CallsSortField>('created', 'desc', []);

  callsPage = signal(1);
  callsTotal = computed(() => this.recent()?.total ?? 0);
  callsTotalPages = computed(() => Math.max(1, Math.ceil(this.callsTotal() / this.recentLimit())));

  private initialized = false;

  /** Driven from the component's ngOnInit; `refresh()` stays callable on its own. */
  init(): void {
    if (this.initialized) return;
    this.initialized = true;
    this.refresh();
  }

  refresh(): void {
    this.loading.set(true);
    this.error.set('');
    this.api
      .summary()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (s) => this.summary.set(s),
        error: (err: HttpErrorResponse) =>
          this.error.set(err?.error?.detail ?? 'Failed to load summary'),
      });
    this.loadTimeseries();
    this.loadBreakdown();
    this.loadRecent();
  }

  setRange(days: number): void {
    this.rangeDays.set(days);
    this.loadTimeseries();
    this.loadBreakdown();
  }

  setDimension(d: Dimension): void {
    this.dimension.set(d);
    this.loadBreakdown();
  }

  private loadTimeseries(): void {
    this.api
      .timeseries(this.rangeDays())
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (ts) => {
          this.timeseries.set(ts);
          this.loading.set(false);
        },
        error: (err: HttpErrorResponse) => {
          this.error.set(err?.error?.detail ?? 'Failed to load timeseries');
          this.loading.set(false);
        },
      });
  }

  private loadBreakdown(): void {
    this.api
      .breakdown(this.dimension(), this.rangeDays())
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (b) => this.breakdown.set(b),
        error: (err: HttpErrorResponse) =>
          this.error.set(err?.error?.detail ?? 'Failed to load breakdown'),
      });
  }

  loadRecent(): void {
    this.api
      .recentCalls({
        limit: this.recentLimit(),
        offset: (this.callsPage() - 1) * this.recentLimit(),
        provider: this.filterProvider() || undefined,
        model: this.filterModel() || undefined,
        feature_key: this.filterFeature() || undefined,
        sort: this.callsSort.token(),
      })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (r) => this.recent.set(r),
        error: (err: HttpErrorResponse) =>
          this.error.set(err?.error?.detail ?? 'Failed to load calls'),
      });
  }

  goToCallsPage(page: number): void {
    this.callsPage.set(page);
    this.loadRecent();
  }

  setCallsPageSize(size: number): void {
    this.recentLimit.set(size);
    this.callsPage.set(1);
    this.loadRecent();
  }

  /**
   * Re-query from page 1.
   *
   * Anything that changes which rows match — the filter form, a sort header —
   * must reset the offset, otherwise the user stays on page 5 of a result set
   * that may now be one page long and sees an empty table.
   */
  reloadRecent(): void {
    this.callsPage.set(1);
    this.loadRecent();
  }

  exportCsvUrl(): string {
    return this.api.exportCsvUrl({
      provider: this.filterProvider() || undefined,
      model: this.filterModel() || undefined,
      feature_key: this.filterFeature() || undefined,
      days: 90,
    });
  }
}
