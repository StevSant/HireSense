import { TestBed } from '@angular/core/testing';
import { of, throwError } from 'rxjs';

import { AdminUsageComponent } from './admin-usage.component';
import { AdminUsageService } from '../../core/services/admin-usage.service';
import { BreakdownResponse } from './models/breakdown-response.model';
import { DashboardSummary } from './models/dashboard-summary.model';
import { RecentCallsResponse } from './models/recent-calls-response.model';
import { TimeseriesResponse } from './models/timeseries-response.model';

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

const TIMESERIES: TimeseriesResponse = {
  days: 30,
  buckets: [
    {
      key: '2026-06-01 00:00:00+00',
      calls: 3,
      input_tokens: 300,
      output_tokens: 150,
      total_tokens: 450,
      cost_usd: 0.5,
    },
    {
      key: '2026-06-02 00:00:00+00',
      calls: 7,
      input_tokens: 700,
      output_tokens: 350,
      total_tokens: 1050,
      cost_usd: 1.0,
    },
  ],
};

const BREAKDOWN_FEATURE: BreakdownResponse = {
  dimension: 'feature',
  days: 30,
  buckets: [
    {
      key: 'matching.score',
      calls: 8,
      input_tokens: 800,
      output_tokens: 400,
      total_tokens: 1200,
      cost_usd: 1.0,
    },
  ],
};

const BREAKDOWN_PROVIDER: BreakdownResponse = {
  dimension: 'provider',
  days: 30,
  buckets: [
    {
      key: 'anthropic',
      calls: 5,
      input_tokens: 500,
      output_tokens: 250,
      total_tokens: 750,
      cost_usd: 0.8,
    },
  ],
};

const RECENT: RecentCallsResponse = {
  limit: 50,
  offset: 0,
  calls: [
    {
      id: 'c1',
      created_at: '2026-06-02T10:00:00Z',
      feature_key: 'matching.score',
      provider: 'anthropic',
      model: 'claude-opus-4-7',
      input_tokens: 100,
      output_tokens: 50,
      total_tokens: 150,
      cost_usd: 0.01,
      latency_ms: 250,
      success: true,
      error: null,
    },
  ],
};

describe('AdminUsageComponent', () => {
  let summary: ReturnType<typeof vi.fn>;
  let timeseries: ReturnType<typeof vi.fn>;
  let breakdown: ReturnType<typeof vi.fn>;
  let recentCalls: ReturnType<typeof vi.fn>;
  let exportCsvUrl: ReturnType<typeof vi.fn>;

  beforeEach(async () => {
    summary = vi.fn().mockReturnValue(of(SUMMARY));
    timeseries = vi.fn().mockReturnValue(of(TIMESERIES));
    breakdown = vi.fn().mockReturnValue(of(BREAKDOWN_FEATURE));
    recentCalls = vi.fn().mockReturnValue(of(RECENT));
    exportCsvUrl = vi.fn().mockReturnValue('http://x/export?days=90');

    await TestBed.configureTestingModule({
      imports: [AdminUsageComponent],
      providers: [
        {
          provide: AdminUsageService,
          useValue: { summary, timeseries, breakdown, recentCalls, exportCsvUrl },
        },
      ],
    }).compileComponents();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  function mount() {
    const fixture = TestBed.createComponent(AdminUsageComponent);
    fixture.detectChanges();
    return fixture;
  }

  describe('initial load', () => {
    it('loads all four panels and populates the signals', () => {
      const fixture = mount();
      const c = fixture.componentInstance;

      expect(summary).toHaveBeenCalled();
      expect(timeseries).toHaveBeenCalledWith(30);
      expect(breakdown).toHaveBeenCalledWith('feature', 30);
      expect(recentCalls).toHaveBeenCalled();

      expect(c.summary()).toEqual(SUMMARY);
      expect(c.timeseries()).toEqual(TIMESERIES);
      expect(c.breakdown()).toEqual(BREAKDOWN_FEATURE);
      expect(c.recent()).toEqual(RECENT);
      expect(c.loading()).toBe(false);
      expect(c.error()).toBe('');
    });

    it('renders the KPI cards and the recent-calls row', () => {
      const fixture = mount();
      const el: HTMLElement = fixture.nativeElement;
      expect(el.querySelectorAll('.kpi-card').length).toBe(3);
      const callRows = el.querySelectorAll('.calls-table tbody tr');
      expect(callRows.length).toBe(1);
      expect(el.querySelector('.badge.success')).not.toBeNull();
    });

    it('derives the max bucket cost for chart scaling', () => {
      const fixture = mount();
      expect(fixture.componentInstance.maxBucketCost()).toBe(1.0);
      expect(fixture.componentInstance.maxBreakdownCost()).toBe(1.0);
    });
  });

  describe('breakdown rendering', () => {
    it('renders one row per breakdown bucket', () => {
      const fixture = mount();
      const rows = fixture.nativeElement.querySelectorAll('.breakdown-table tbody tr');
      expect(rows.length).toBe(1);
      expect(
        fixture.nativeElement.querySelector('.breakdown-table tbody code').textContent,
      ).toContain('matching.score');
    });

    it('shows the empty state when there are no breakdown buckets', () => {
      breakdown.mockReturnValue(of({ ...BREAKDOWN_FEATURE, buckets: [] }));
      const fixture = mount();
      const empties = Array.from(fixture.nativeElement.querySelectorAll('.empty')) as HTMLElement[];
      expect(empties.some((e) => e.textContent?.includes('No usage to break down'))).toBe(true);
    });
  });

  describe('dimension toggle', () => {
    it('reloads the breakdown for the selected dimension', () => {
      const fixture = mount();
      const c = fixture.componentInstance;
      breakdown.mockReturnValue(of(BREAKDOWN_PROVIDER));

      c.setDimension('provider');
      fixture.detectChanges();

      expect(c.dimension()).toBe('provider');
      expect(breakdown).toHaveBeenLastCalledWith('provider', 30);
      expect(c.breakdown()).toEqual(BREAKDOWN_PROVIDER);
      // summary/timeseries/recent are NOT re-fetched on a dimension change
      expect(summary).toHaveBeenCalledTimes(1);
      expect(timeseries).toHaveBeenCalledTimes(1);
    });
  });

  describe('range toggle', () => {
    it('reloads timeseries and breakdown for the new range', () => {
      const fixture = mount();
      const c = fixture.componentInstance;

      c.setRange(7);

      expect(c.rangeDays()).toBe(7);
      expect(timeseries).toHaveBeenLastCalledWith(7);
      expect(breakdown).toHaveBeenLastCalledWith('feature', 7);
    });
  });

  describe('error states', () => {
    it('sets an error when the summary request fails', () => {
      summary.mockReturnValue(throwError(() => ({ error: { detail: 'summary down' } })));
      const fixture = mount();
      expect(fixture.componentInstance.error()).toBe('summary down');
    });

    it('sets an error and clears loading when timeseries fails', () => {
      timeseries.mockReturnValue(throwError(() => new Error('ts fail')));
      const fixture = mount();
      expect(fixture.componentInstance.error()).toBe('Failed to load timeseries');
      expect(fixture.componentInstance.loading()).toBe(false);
    });
  });

  describe('csv export', () => {
    it('opens the export url built from the current filters', () => {
      const openSpy = vi.spyOn(window, 'open').mockReturnValue(null);
      const fixture = mount();
      fixture.componentInstance.filterProvider.set('anthropic');
      fixture.componentInstance.exportCsv();

      expect(exportCsvUrl).toHaveBeenCalledWith(
        expect.objectContaining({ provider: 'anthropic', days: 90 }),
      );
      expect(openSpy).toHaveBeenCalledWith('http://x/export?days=90', '_blank');
    });
  });
});
