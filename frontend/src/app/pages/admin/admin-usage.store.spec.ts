import { TestBed } from '@angular/core/testing';
import { Observable, of, throwError } from 'rxjs';
import { AdminUsageService } from '../../core/services/admin-usage.service';
import { BreakdownResponse } from '@core/contracts/breakdown-response.model';
import { DashboardSummary } from '@core/contracts/dashboard-summary.model';
import { RecentCallsResponse } from '@core/contracts/recent-calls-response.model';
import { TimeseriesResponse } from '@core/contracts/timeseries-response.model';
import { UsageBucket } from '@core/contracts/usage-bucket.model';
import { AdminUsageStore } from './admin-usage.store';

const TOTALS = {
  total_calls: 10,
  total_input_tokens: 1000,
  total_output_tokens: 500,
  total_tokens: 1500,
  total_cost_usd: 1.2345,
};

const SUMMARY: DashboardSummary = {
  today: TOTALS,
  this_month: TOTALS,
  all_time: TOTALS,
};

function makeBucket(key: string, over: Partial<UsageBucket> = {}): UsageBucket {
  return {
    key,
    calls: 1,
    input_tokens: 100,
    output_tokens: 50,
    total_tokens: 150,
    cost_usd: 0.5,
    ...over,
  };
}

const TIMESERIES: TimeseriesResponse = {
  days: 30,
  buckets: [makeBucket('2026-06-01', { cost_usd: 0.5 }), makeBucket('2026-06-02', { cost_usd: 1 })],
};

const BREAKDOWN: BreakdownResponse = {
  dimension: 'feature',
  days: 30,
  buckets: [makeBucket('matching.score', { cost_usd: 1 })],
};

function makeRecent(over: Partial<RecentCallsResponse> = {}): RecentCallsResponse {
  return { calls: [], limit: 50, offset: 0, total: 1, ...over };
}

interface SetupOptions {
  readonly summary?: () => Observable<DashboardSummary>;
  readonly timeseries?: () => Observable<TimeseriesResponse>;
  readonly breakdown?: () => Observable<BreakdownResponse>;
  readonly recentCalls?: () => Observable<RecentCallsResponse>;
}

function setup(over: SetupOptions = {}) {
  const summary = vi.fn(over.summary ?? ((): Observable<DashboardSummary> => of(SUMMARY)));
  const timeseries = vi.fn(
    over.timeseries ?? ((): Observable<TimeseriesResponse> => of(TIMESERIES)),
  );
  const breakdown = vi.fn(over.breakdown ?? ((): Observable<BreakdownResponse> => of(BREAKDOWN)));
  const recentCalls = vi.fn(
    over.recentCalls ?? ((): Observable<RecentCallsResponse> => of(makeRecent())),
  );
  const exportCsvUrl = vi.fn(() => 'https://example.test/api/admin/usage/export?days=90');

  TestBed.configureTestingModule({
    providers: [
      AdminUsageStore,
      {
        provide: AdminUsageService,
        useValue: { summary, timeseries, breakdown, recentCalls, exportCsvUrl },
      },
    ],
  });

  return {
    store: TestBed.inject(AdminUsageStore),
    summary,
    timeseries,
    breakdown,
    recentCalls,
    exportCsvUrl,
  };
}

describe('AdminUsageStore loading', () => {
  it('ignores a second init so the panels are not fetched twice', () => {
    const { store, summary, timeseries, breakdown, recentCalls } = setup();

    store.init();
    store.init();

    expect(summary).toHaveBeenCalledTimes(1);
    expect(timeseries).toHaveBeenCalledTimes(1);
    expect(breakdown).toHaveBeenCalledTimes(1);
    expect(recentCalls).toHaveBeenCalledTimes(1);
  });

  it('reloads only the range-dependent panels when the range changes', () => {
    const { store, summary, timeseries, breakdown, recentCalls } = setup();
    store.init();

    store.setRange(7);

    expect(store.rangeDays()).toBe(7);
    expect(timeseries).toHaveBeenLastCalledWith(7);
    expect(breakdown).toHaveBeenLastCalledWith('feature', 7);
    // The summary is all-time and the calls table has its own paging, so
    // neither is re-queried for a range change.
    expect(summary).toHaveBeenCalledTimes(1);
    expect(recentCalls).toHaveBeenCalledTimes(1);
  });

  it('reloads only the breakdown when the dimension changes', () => {
    const { store, timeseries, breakdown } = setup();
    store.init();

    store.setDimension('provider');

    expect(breakdown).toHaveBeenLastCalledWith('provider', 30);
    expect(timeseries).toHaveBeenCalledTimes(1);
  });

  it('clears a previous error when the dashboard is refreshed', () => {
    const { store, summary } = setup({
      summary: () => throwError(() => ({ error: { detail: 'summary down' } })),
    });
    store.init();
    expect(store.error()).toBe('summary down');

    summary.mockImplementation(() => of(SUMMARY));
    store.refresh();

    expect(store.error()).toBe('');
    expect(store.summary()).toEqual(SUMMARY);
  });
});

describe('AdminUsageStore chart scaling', () => {
  it('floors the chart scale so an empty range cannot divide by zero', () => {
    const { store } = setup({
      timeseries: () => of({ days: 30, buckets: [] }),
      breakdown: () => of({ dimension: 'feature', days: 30, buckets: [] }),
    });

    store.init();

    expect(store.maxBucketCost()).toBe(0.0001);
    expect(store.maxBreakdownCost()).toBe(0.0001);
  });

  it('scales to the most expensive bucket in each panel', () => {
    const { store } = setup();

    store.init();

    expect(store.maxBucketCost()).toBe(1);
    expect(store.maxBreakdownCost()).toBe(1);
  });
});

describe('AdminUsageStore breakdown sorting', () => {
  function setupWithBuckets() {
    return setup({
      breakdown: () =>
        of({
          dimension: 'feature',
          days: 30,
          buckets: [
            makeBucket('zeta', { calls: 1, cost_usd: 0.5, total_tokens: 300 }),
            makeBucket('alpha', { calls: 9, cost_usd: 2, total_tokens: 100 }),
            makeBucket('mid', { calls: 5, cost_usd: 1, total_tokens: 200 }),
          ],
        } as BreakdownResponse),
    });
  }

  it('ranks the buckets by cost descending by default', () => {
    const { store } = setupWithBuckets();
    store.init();

    expect(store.visibleBuckets().map((b) => b.key)).toEqual(['alpha', 'mid', 'zeta']);
  });

  it('sorts the key column alphabetically and numeric columns high-to-low first', () => {
    const { store, breakdown } = setupWithBuckets();
    store.init();

    store.breakdownSort.toggle('key');
    expect(store.visibleBuckets().map((b) => b.key)).toEqual(['alpha', 'mid', 'zeta']);

    store.breakdownSort.toggle('key'); // same column flips to descending
    expect(store.visibleBuckets().map((b) => b.key)).toEqual(['zeta', 'mid', 'alpha']);

    store.breakdownSort.toggle('calls');
    expect(store.visibleBuckets().map((b) => b.key)).toEqual(['alpha', 'mid', 'zeta']);

    store.breakdownSort.toggle('total_tokens');
    expect(store.visibleBuckets().map((b) => b.key)).toEqual(['zeta', 'mid', 'alpha']);

    // Sorting the already-aggregated buckets never goes back to the server.
    expect(breakdown).toHaveBeenCalledTimes(1);
  });
});

describe('AdminUsageStore recent calls', () => {
  it('requests the first page with the default sort and no filters', () => {
    const { store, recentCalls } = setup();

    store.init();

    expect(recentCalls).toHaveBeenCalledWith(
      expect.objectContaining({ limit: 50, offset: 0, sort: 'created_desc' }),
    );
  });

  it('turns the page into an offset', () => {
    const { store, recentCalls } = setup();
    store.init();

    store.goToCallsPage(3);

    expect(store.callsPage()).toBe(3);
    expect(recentCalls).toHaveBeenLastCalledWith(
      expect.objectContaining({ limit: 50, offset: 100 }),
    );
  });

  it('returns to the first page when the page size changes', () => {
    const { store, recentCalls } = setup();
    store.init();
    store.goToCallsPage(3);

    store.setCallsPageSize(25);

    expect(store.callsPage()).toBe(1);
    expect(recentCalls).toHaveBeenLastCalledWith(expect.objectContaining({ limit: 25, offset: 0 }));
  });

  it('re-queries from the first page when the filters or sort change', () => {
    const { store, recentCalls } = setup();
    store.init();
    store.goToCallsPage(4);

    store.filterProvider.set('anthropic');
    store.callsSort.toggle('cost');
    store.reloadRecent();

    expect(store.callsPage()).toBe(1);
    expect(recentCalls).toHaveBeenLastCalledWith(
      expect.objectContaining({
        offset: 0,
        provider: 'anthropic',
        sort: 'cost_desc',
      }),
    );
  });

  it('omits filters that are blank', () => {
    const { store, recentCalls } = setup();
    store.init();

    store.filterModel.set('claude-opus-4-7');
    store.reloadRecent();

    expect(recentCalls).toHaveBeenLastCalledWith(
      expect.objectContaining({
        provider: undefined,
        model: 'claude-opus-4-7',
        feature_key: undefined,
      }),
    );
  });

  it('derives the page count from the server total and the page size', () => {
    const { store } = setup({ recentCalls: () => of(makeRecent({ total: 120 })) });
    store.init();

    expect(store.callsTotal()).toBe(120);
    expect(store.callsTotalPages()).toBe(3);

    store.setCallsPageSize(100);

    expect(store.callsTotalPages()).toBe(2);
  });

  it('reports at least one page when there are no calls at all', () => {
    const { store } = setup({ recentCalls: () => of(makeRecent({ total: 0 })) });

    store.init();

    expect(store.callsTotal()).toBe(0);
    expect(store.callsTotalPages()).toBe(1);
  });

  it('keeps the loaded calls on screen when a later page fails', () => {
    const { store, recentCalls } = setup({
      recentCalls: () => of(makeRecent({ total: 120 })),
    });
    store.init();
    const loaded = store.recent();

    recentCalls.mockImplementation(() => throwError(() => ({ error: { detail: 'calls down' } })));
    store.goToCallsPage(2);

    expect(store.error()).toBe('calls down');
    expect(store.recent()).toBe(loaded);
  });

  it('builds the export url from the active filters over a fixed window', () => {
    const { store, exportCsvUrl } = setup();
    store.init();
    store.filterProvider.set('anthropic');
    store.filterFeature.set('matching.score');

    const url = store.exportCsvUrl();

    expect(exportCsvUrl).toHaveBeenCalledWith({
      provider: 'anthropic',
      model: undefined,
      feature_key: 'matching.score',
      days: 90,
    });
    expect(url).toBe('https://example.test/api/admin/usage/export?days=90');
  });
});
