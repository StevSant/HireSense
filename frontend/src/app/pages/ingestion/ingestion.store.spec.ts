import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, Router } from '@angular/router';
import { Observable, Subject, of, throwError } from 'rxjs';
import { ApplicationsService } from '../../core/services/applications.service';
import { IngestionService } from '../../core/services/ingestion.service';
import { NormalizedJob } from '@core/contracts/normalized-job.model';
import { PaginatedJobsResponse } from '@core/contracts/paginated-jobs-response.model';
import { PortalEntry } from '@core/contracts/portal-entry.model';
import { ScanResult } from '@core/contracts/scan-result.model';
import {
  IntegrationMethod,
  SourceHealth,
  SourceHealthStatus,
  SourceInfo,
  SourcesHealthResponse,
  SourcesResponse,
} from '@core/contracts/source-capability.model';
import { FetchResponse } from '@core/contracts/fetch-response.model';
import { IngestionStore } from './ingestion.store';
import { environment } from '../../../environments/environment';
import { RevalidationStatus } from '@core/contracts/revalidation-status.model';

interface RevalidateResponse {
  started: boolean;
  closed: number;
  closed_ids: string[];
}

function makeJob(over: Partial<NormalizedJob> = {}): NormalizedJob {
  return {
    id: 'job-1',
    title: 'Engineer',
    company: 'Acme',
    description: 'Build things.',
    skills: ['python'],
    location: 'Remote',
    salary_range: null,
    source: 'remotive',
    source_type: 'feed',
    platform: null,
    categories: [],
    department: null,
    url: 'https://example.com/job-1',
    posted_date: null,
    match_score: 0.8,
    llm_score: 0.8,
    verdict: 'strong',
    reasons: [],
    dealbreakers: [],
    status: 'open',
    ...over,
  };
}

function makePage(
  jobs: NormalizedJob[],
  over: Partial<PaginatedJobsResponse> = {},
): PaginatedJobsResponse {
  return {
    jobs,
    total: jobs.length,
    page: 1,
    page_size: 20,
    total_pages: 1,
    ...over,
  };
}

function makeSource(
  source: string,
  over: {
    enabled?: boolean;
    wired?: boolean;
    requiresCredentials?: boolean;
    integration?: IntegrationMethod;
  } = {},
): SourceInfo {
  return {
    capabilities: {
      source,
      display_name: source,
      source_type: 'api',
      integration: over.integration ?? 'official_api',
      enabled_by_default: true,
      requires_credentials: over.requiresCredentials ?? false,
      supports_keyword_search: true,
      supports_location_search: false,
      supports_remote_filter: false,
      supports_pagination: false,
      provides_salary: false,
      provides_equity: false,
      provides_company_metadata: false,
      provides_technology_tags: false,
      snapshot_source: false,
      reliable_closure_detection: false,
      closure_strategy: 'url_probe',
      limitations: '',
    },
    enabled: over.enabled ?? true,
    wired: over.wired ?? true,
  };
}

function makeHealth(source: string, status: SourceHealthStatus): SourceHealth {
  return {
    source,
    status,
    last_attempt_at: null,
    last_success_at: null,
    duration_ms: null,
    pages_fetched: 0,
    jobs_discovered: 0,
    jobs_created: 0,
    jobs_updated: 0,
    jobs_deduplicated: 0,
    jobs_rejected_malformed: 0,
    rate_limited_count: 0,
    parse_failures: 0,
    last_error: null,
  };
}

function makeScanResult(over: Partial<ScanResult> = {}): ScanResult {
  return { total_fetched: 5, new: 2, duplicates: 1, jobs: [], errors: [], ...over };
}

interface SetupOptions {
  readonly queryJobs?: () => Observable<PaginatedJobsResponse>;
  readonly fetchJobs?: () => Observable<FetchResponse>;
  readonly revalidate?: () => Observable<RevalidateResponse>;
  readonly revalidationStatus?: () => Observable<RevalidationStatus>;
  readonly loadPortals?: () => Observable<PortalEntry[]>;
  readonly listSources?: () => Observable<SourcesResponse>;
  readonly sourcesHealth?: () => Observable<SourcesHealthResponse>;
  readonly scanPortals?: () => Observable<ScanResult>;
  readonly getJob?: () => Observable<NormalizedJob>;
  readonly createFromJob?: () => Observable<{ id: string }>;
  readonly queryParams?: Readonly<Record<string, string>>;
}

function setup(over: SetupOptions = {}) {
  const trackedJobIds = signal<Set<string>>(new Set<string>());

  const queryJobs = vi.fn(over.queryJobs ?? (() => of(makePage([makeJob()]))));
  const fetchJobs = vi.fn(
    over.fetchJobs ?? ((): Observable<FetchResponse> => of({ count: 0, jobs: [] })),
  );
  const revalidate = vi.fn(
    over.revalidate ??
      ((): Observable<RevalidateResponse> => of({ started: true, closed: 0, closed_ids: [] })),
  );
  const revalidationStatus = vi.fn(
    over.revalidationStatus ??
      ((): Observable<RevalidationStatus> =>
        of({ sweeping: false, checked: 0, total: 0, closed: 0 })),
  );
  const loadPortals = vi.fn(over.loadPortals ?? (() => of<PortalEntry[]>([])));
  const listSources = vi.fn(
    over.listSources ?? ((): Observable<SourcesResponse> => of({ sources: [] })),
  );
  const sourcesHealth = vi.fn(
    over.sourcesHealth ?? ((): Observable<SourcesHealthResponse> => of({ sources: [] })),
  );
  const scanPortals = vi.fn(over.scanPortals ?? (() => of(makeScanResult())));
  const getJob = vi.fn(over.getJob ?? (() => of(makeJob())));
  const markTracked = vi.fn((jobId: string) =>
    trackedJobIds.update((ids) => new Set([...ids, jobId])),
  );
  const createFromJob = vi.fn(over.createFromJob ?? (() => of({ id: 'app-1' })));
  const navigate = vi.fn();

  const params = over.queryParams ?? {};
  const route = {
    snapshot: { queryParamMap: { get: (key: string) => params[key] ?? null } },
  };

  TestBed.configureTestingModule({
    providers: [
      IngestionStore,
      {
        provide: IngestionService,
        useValue: {
          trackedJobIds,
          queryJobs,
          fetchJobs,
          revalidate,
          revalidationStatus,
          loadPortals,
          listSources,
          sourcesHealth,
          scanPortals,
          getJob,
          markTracked,
        },
      },
      { provide: ApplicationsService, useValue: { createFromJob } },
      { provide: Router, useValue: { navigate } },
      { provide: ActivatedRoute, useValue: route },
    ],
  });

  return {
    store: TestBed.inject(IngestionStore),
    queryJobs,
    fetchJobs,
    revalidate,
    revalidationStatus,
    loadPortals,
    listSources,
    sourcesHealth,
    scanPortals,
    getJob,
    markTracked,
    createFromJob,
    navigate,
  };
}

// The argument list `queryJobs` is called with for a default, unfiltered load.
const DEFAULT_SORT_FILTERS = { sort: 'match_desc' };

describe('IngestionStore bootstrap', () => {
  it('loads portals, the source catalog and source health without querying jobs', () => {
    const { store, loadPortals, listSources, sourcesHealth, queryJobs } = setup();

    store.init();

    expect(loadPortals).toHaveBeenCalledTimes(1);
    expect(listSources).toHaveBeenCalledTimes(1);
    expect(sourcesHealth).toHaveBeenCalledTimes(1);
    // The first job load is driven by <app-job-filters>'s initial emission, so
    // init() itself must never issue one — otherwise two requests race.
    expect(queryJobs).not.toHaveBeenCalled();
  });

  it('ignores a second init so the bootstrap requests are not duplicated', () => {
    const { store, loadPortals, listSources } = setup();

    store.init();
    store.init();

    expect(loadPortals).toHaveBeenCalledTimes(1);
    expect(listSources).toHaveBeenCalledTimes(1);
  });

  it('seeds the keyword filter from the keyword query param', () => {
    const { store } = setup({ queryParams: { keyword: 'rust' } });

    store.init();

    expect(store.filters().keyword).toBe('rust');
  });

  it('leaves the filters empty when there is no keyword query param', () => {
    const { store } = setup();

    store.init();

    expect(store.filters()).toEqual({});
  });

  it('opens the detail panel for the job_id query param', () => {
    const { store, getJob } = setup({
      queryParams: { job_id: 'job-7' },
      getJob: () => of(makeJob({ id: 'job-7' })),
    });

    store.init();

    expect(getJob).toHaveBeenCalledWith('job-7');
    expect(store.selectedJob()?.id).toBe('job-7');
  });

  it('leaves the detail panel closed when the job_id lookup fails', () => {
    const { store } = setup({
      queryParams: { job_id: 'gone' },
      getJob: () => throwError(() => ({ status: 404 })),
    });

    store.init();

    expect(store.selectedJob()).toBeNull();
  });
});

describe('IngestionStore job list', () => {
  it('populates rows, totals and connections and clears the spinner', () => {
    const { store } = setup({
      queryJobs: () =>
        of(
          makePage([makeJob(), makeJob({ id: 'job-2' })], {
            total: 42,
            total_pages: 3,
            connections_by_job: { 'job-1': 3 },
          }),
        ),
    });
    store.init();

    store.loadJobs();

    expect(store.jobs().map((j) => j.id)).toEqual(['job-1', 'job-2']);
    expect(store.total()).toBe(42);
    expect(store.totalPages()).toBe(3);
    expect(store.connectionsCount('job-1')).toBe(3);
    expect(store.connectionsCount('job-2')).toBeUndefined();
    expect(store.loading()).toBe(false);
    expect(store.error()).toBe('');
  });

  it('defaults the connections map to empty when the response omits it', () => {
    const { store } = setup({ queryJobs: () => of(makePage([makeJob()])) });
    store.init();

    store.loadJobs();

    expect(store.connectionsByJob()).toEqual({});
  });

  it('keeps the previously loaded rows and clears the spinner when a load fails', () => {
    const { store, queryJobs } = setup();
    store.init();
    store.loadJobs();
    expect(store.jobs().length).toBe(1);

    queryJobs.mockImplementation(() => throwError(() => ({ error: { detail: 'boom' } })));
    store.loadJobs();

    expect(store.error()).toBe('boom');
    expect(store.loading()).toBe(false);
    // A failed refresh must not blank a list the user is still reading.
    expect(store.jobs().length).toBe(1);
  });

  it('falls back to a generic message when the failed load carries no detail', () => {
    const { store } = setup({ queryJobs: () => throwError(() => new Error('offline')) });
    store.init();

    store.loadJobs();

    expect(store.error()).toBe('Failed to load jobs');
    expect(store.loading()).toBe(false);
  });

  it('clears a previous error once a later load succeeds', () => {
    const { store, queryJobs } = setup({
      queryJobs: () => throwError(() => ({ error: { detail: 'boom' } })),
    });
    store.init();
    store.loadJobs();
    expect(store.error()).toBe('boom');

    queryJobs.mockImplementation(() => of(makePage([makeJob()])));
    store.loadJobs();

    expect(store.error()).toBe('');
    expect(store.jobs().length).toBe(1);
  });

  it('applies only the newest request when two loads overlap', () => {
    const pending: Subject<PaginatedJobsResponse>[] = [];
    const { store } = setup({
      queryJobs: () => {
        const subject = new Subject<PaginatedJobsResponse>();
        pending.push(subject);
        return subject.asObservable();
      },
    });
    store.init();

    store.loadJobs();
    store.loadJobs();
    expect(pending.length).toBe(2);

    pending[1].next(makePage([makeJob({ id: 'winner' })]));
    // The first request was cancelled by switchMap; a late emission on it must
    // not overwrite the newer result.
    pending[0].next(makePage([makeJob({ id: 'loser' })]));

    expect(store.jobs().map((j) => j.id)).toEqual(['winner']);
    expect(store.loading()).toBe(false);
  });

  it('holds the spinner up while a request is still in flight', () => {
    const { store } = setup({ queryJobs: () => new Subject<PaginatedJobsResponse>() });
    store.init();

    store.loadJobs();

    expect(store.loading()).toBe(true);
  });
});

describe('IngestionStore query shape', () => {
  it('folds the applied filters and the sort token into the request and resets the page', () => {
    const { store, queryJobs } = setup();
    store.init();
    store.goToPage(4);

    store.applyFilters({ keyword: 'rust', company: 'Acme' });

    expect(store.page()).toBe(1);
    expect(queryJobs).toHaveBeenLastCalledWith(
      'boards',
      1,
      20,
      { keyword: 'rust', company: 'Acme', sort: 'match_desc' },
      false,
      true,
      false,
    );
  });

  it('sends the toggled sort token and reuses cached scores for a reorder', () => {
    const { store, queryJobs } = setup();
    store.init();

    store.sort.toggle('title');
    store.applySort();

    // 'title' is a text column, so a fresh selection defaults to ascending.
    expect(queryJobs).toHaveBeenLastCalledWith(
      'boards',
      1,
      20,
      { sort: 'title_asc' },
      false,
      false,
      false,
    );
  });

  it('reuses cached scores for pagination', () => {
    const { store, queryJobs } = setup();
    store.init();

    store.goToPage(3);

    expect(store.page()).toBe(3);
    expect(queryJobs).toHaveBeenLastCalledWith(
      'boards',
      3,
      20,
      DEFAULT_SORT_FILTERS,
      false,
      false,
      false,
    );
  });

  it('resets to the first page and reuses cached scores when the page size changes', () => {
    const { store, queryJobs } = setup();
    store.init();
    store.goToPage(3);

    store.setPageSize(50);

    expect(store.page()).toBe(1);
    expect(queryJobs).toHaveBeenLastCalledWith(
      'boards',
      1,
      50,
      DEFAULT_SORT_FILTERS,
      false,
      false,
      false,
    );
  });

  it('clears the filters and resets the page when the tab changes', () => {
    const { store, queryJobs } = setup();
    store.init();
    store.applyFilters({ keyword: 'rust' });
    store.goToPage(2);

    store.switchTab('portals');

    expect(store.activeTab()).toBe('portals');
    expect(store.filters()).toEqual({});
    expect(queryJobs).toHaveBeenLastCalledWith(
      'portals',
      1,
      20,
      DEFAULT_SORT_FILTERS,
      false,
      true,
      false,
    );
  });

  it('rescores from page one when the closed-jobs toggle changes', () => {
    const { store, queryJobs } = setup();
    store.init();
    store.goToPage(2);

    store.setIncludeClosed(true);

    expect(store.includeClosed()).toBe(true);
    expect(queryJobs).toHaveBeenLastCalledWith(
      'boards',
      1,
      20,
      DEFAULT_SORT_FILTERS,
      true,
      true,
      false,
    );
  });

  it('rescores from page one when the low-quality toggle changes', () => {
    const { store, queryJobs } = setup();
    store.init();
    store.goToPage(2);

    store.setIncludeLowQuality(true);

    expect(store.includeLowQuality()).toBe(true);
    expect(queryJobs).toHaveBeenLastCalledWith(
      'boards',
      1,
      20,
      DEFAULT_SORT_FILTERS,
      false,
      true,
      true,
    );
  });
});

describe('IngestionStore source catalog', () => {
  it('lists only usable, non-ATS sources in the board dropdown', () => {
    const { store } = setup({
      listSources: () =>
        of({
          sources: [
            makeSource('remotive'),
            makeSource('greenhouse'),
            makeSource('linkedin', { wired: false, requiresCredentials: true }),
            makeSource('retired', { enabled: false, wired: false }),
          ],
        }),
    });

    store.init();

    // greenhouse is scanned from the Portals tab, not the Boards dropdown;
    // 'retired' is neither enabled nor wired.
    expect(store.boardSources()).toEqual(['remotive', 'linkedin']);
  });

  it('reports failing, degraded and credential-blocked sources as warnings', () => {
    const { store } = setup({
      listSources: () =>
        of({
          sources: [
            makeSource('remotive'),
            makeSource('linkedin', { wired: false, requiresCredentials: true }),
            makeSource('workday', { wired: false, integration: 'import_fallback' }),
            makeSource('retired', { enabled: false, wired: false, requiresCredentials: true }),
          ],
        }),
      sourcesHealth: () =>
        of({
          sources: [
            makeHealth('remotive', 'failing'),
            makeHealth('jobicy', 'degraded'),
            makeHealth('weworkremotely', 'healthy'),
          ],
        }),
    });

    store.init();

    const warnings = store.sourceWarnings();
    expect(warnings.failing.map((h) => h.source)).toEqual(['remotive', 'jobicy']);
    expect(warnings.unavailable.map((s) => s.capabilities.source)).toEqual(['linkedin', 'workday']);
  });

  it('leaves the board dropdown empty rather than guessing when the catalog fails', () => {
    const { store } = setup({
      listSources: () => throwError(() => ({ status: 500 })),
      sourcesHealth: () => throwError(() => ({ status: 500 })),
    });

    store.init();

    expect(store.boardSources()).toEqual([]);
    expect(store.sourceHealth()).toEqual([]);
    expect(store.sourceWarnings().failing).toEqual([]);
  });
});

describe('IngestionStore portals and scanning', () => {
  const portals: PortalEntry[] = [
    { name: 'Acme', platform: 'greenhouse', board_id: 'acme', categories: ['eng', 'design'] },
    { name: 'Globex', platform: 'lever', board_id: 'globex', categories: ['eng'] },
  ];

  it('derives a deduplicated, sorted category list and the portal source names', () => {
    const { store } = setup({ loadPortals: () => of(portals) });

    store.init();

    expect(store.availableCategories()).toEqual(['design', 'eng']);
    expect(store.portalSources()).toEqual(['Acme', 'Globex']);
  });

  it('scans with an empty body when nothing is selected', () => {
    const { store, scanPortals } = setup();
    store.init();
    store.setScanKeyword('   ');

    store.scanPortals();

    expect(scanPortals).toHaveBeenCalledWith({});
  });

  it('sends only the selections that are set, with the keyword trimmed', () => {
    const { store, scanPortals } = setup();
    store.init();
    store.setSelectedCategories(['eng']);
    store.setScanKeyword('  rust  ');

    store.scanPortals();

    expect(scanPortals).toHaveBeenCalledWith({ categories: ['eng'], keyword: 'rust' });
  });

  it('summarizes a completed scan and refreshes the job list', () => {
    const { store, queryJobs } = setup({
      scanPortals: () => of(makeScanResult({ total_fetched: 9, new: 4, duplicates: 5 })),
    });
    store.init();

    store.scanPortals();

    expect(store.scanSummary()).toBe('Scan complete: 9 fetched, 4 new, 5 duplicates.');
    expect(store.scanning()).toBe(false);
    expect(queryJobs).toHaveBeenCalledTimes(1);
  });

  it('reports a failed scan without refreshing the job list', () => {
    const { store, queryJobs } = setup({
      scanPortals: () => throwError(() => ({ error: { detail: 'portal down' } })),
    });
    store.init();

    store.scanPortals();

    expect(store.scanSummary()).toBe('portal down');
    expect(store.scanning()).toBe(false);
    expect(queryJobs).not.toHaveBeenCalled();
  });

  it('toggles the scan filter panel', () => {
    const { store } = setup();

    expect(store.showScanFilters()).toBe(false);
    store.toggleScanFilters();
    expect(store.showScanFilters()).toBe(true);
    store.toggleScanFilters();
    expect(store.showScanFilters()).toBe(false);
  });
});

describe('IngestionStore fetch', () => {
  it('reports the ingested count and refreshes without paying for a rescore', () => {
    const { store, queryJobs } = setup({ fetchJobs: () => of({ count: 3, jobs: [] }) });
    store.init();

    store.fetchJobs();

    expect(store.fetching()).toBe(false);
    expect(store.fetchNotice()).toContain('3 new job(s)');
    expect(queryJobs).toHaveBeenLastCalledWith(
      'boards',
      1,
      20,
      DEFAULT_SORT_FILTERS,
      false,
      false,
      false,
    );
  });

  it('clears both spinners and skips the refresh when the fetch fails', () => {
    const { store, queryJobs } = setup({
      fetchJobs: () => throwError(() => ({ error: { detail: 'boards unreachable' } })),
    });
    store.init();

    store.fetchJobs();

    expect(store.error()).toBe('boards unreachable');
    expect(store.fetching()).toBe(false);
    expect(store.loading()).toBe(false);
    expect(queryJobs).not.toHaveBeenCalled();
  });
});

describe('IngestionStore closure revalidation', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it('probes the visible jobs once and ignores a second click while in flight', () => {
    const pending = new Subject<RevalidateResponse>();
    const { store, revalidate } = setup({ revalidate: () => pending.asObservable() });
    store.init();
    store.loadJobs();

    store.revalidate();
    store.revalidate();

    expect(revalidate).toHaveBeenCalledTimes(1);
    expect(revalidate).toHaveBeenCalledWith(['job-1']);
    expect(store.revalidating()).toBe(true);
  });

  it('reports the closures and re-reads the page without a rescore', () => {
    const pending = new Subject<RevalidateResponse>();
    const { store, queryJobs } = setup({ revalidate: () => pending.asObservable() });
    store.init();
    store.loadJobs();
    store.revalidate();

    pending.next({ started: true, closed: 2, closed_ids: ['job-1'] });

    expect(store.revalidating()).toBe(false);
    expect(store.revalidateNotice()).toContain('Closed 2 job(s)');
    expect(queryJobs).toHaveBeenCalledTimes(2);
    expect(queryJobs).toHaveBeenLastCalledWith(
      'boards',
      1,
      20,
      DEFAULT_SORT_FILTERS,
      false,
      false,
      false,
    );
  });

  it('reports sweep progress as a ratio while it runs, then a completion notice', () => {
    const statuses: RevalidationStatus[] = [
      { sweeping: true, checked: 100, total: 300, closed: 4 },
      { sweeping: true, checked: 200, total: 300, closed: 9 },
      { sweeping: false, checked: 300, total: 300, closed: 11 },
    ];
    let tick = 0;
    const { store } = setup({
      revalidationStatus: () => of(statuses[Math.min(tick++, statuses.length - 1)]),
    });
    store.init();
    store.loadJobs();
    store.revalidate();

    vi.advanceTimersByTime(environment.closureRevalidatePollMs);
    expect(store.revalidateNotice()).toContain('100 of 300 checked');

    vi.advanceTimersByTime(environment.closureRevalidatePollMs);
    expect(store.revalidateNotice()).toContain('200 of 300 checked');

    vi.advanceTimersByTime(environment.closureRevalidatePollMs);
    expect(store.revalidateNotice()).toBe('Scan complete: 11 listing(s) closed.');
  });

  it('stops polling once the sweep reports it has finished', () => {
    const { store, revalidationStatus } = setup({
      revalidationStatus: () => of({ sweeping: false, checked: 5, total: 5, closed: 0 }),
    });
    store.init();
    store.loadJobs();
    store.revalidate();

    vi.advanceTimersByTime(environment.closureRevalidatePollMs);
    expect(revalidationStatus).toHaveBeenCalledTimes(1);

    // Well past the old 8-tick budget: a settled sweep must not be polled again.
    vi.advanceTimersByTime(environment.closureRevalidatePollMs * 20);
    expect(revalidationStatus).toHaveBeenCalledTimes(1);
  });

  it('re-reads the page only when the closed count moves, not on every tick', () => {
    const statuses: RevalidationStatus[] = [
      { sweeping: true, checked: 100, total: 300, closed: 0 },
      { sweeping: true, checked: 200, total: 300, closed: 0 },
      { sweeping: true, checked: 300, total: 300, closed: 3 },
    ];
    let tick = 0;
    const { store, queryJobs } = setup({
      revalidationStatus: () => of(statuses[Math.min(tick++, statuses.length - 1)]),
    });
    store.init();
    store.loadJobs();
    store.revalidate();
    // init + the immediate post-revalidate read.
    expect(queryJobs).toHaveBeenCalledTimes(2);

    // First tick: closed moved 0 -> 0 relative to the sentinel, so one read.
    vi.advanceTimersByTime(environment.closureRevalidatePollMs);
    expect(queryJobs).toHaveBeenCalledTimes(3);

    // Second tick: still 0 closed — nothing changed, so no re-read (the old
    // version re-ran the whole scored feed here).
    vi.advanceTimersByTime(environment.closureRevalidatePollMs);
    expect(queryJobs).toHaveBeenCalledTimes(3);

    // Third tick: 3 closed — worth re-reading.
    vi.advanceTimersByTime(environment.closureRevalidatePollMs);
    expect(queryJobs).toHaveBeenCalledTimes(4);
  });

  it('clears the spinner and reports the failure without re-reading the page', () => {
    const { store, queryJobs } = setup({
      revalidate: () => throwError(() => ({ error: { detail: 'sweep failed' } })),
    });
    store.init();
    store.loadJobs();

    store.revalidate();

    expect(store.revalidating()).toBe(false);
    expect(store.error()).toBe('sweep failed');
    expect(queryJobs).toHaveBeenCalledTimes(1);
  });
});

describe('IngestionStore tracking', () => {
  it('marks the job tracked and opens the new application', () => {
    const { store, navigate, markTracked } = setup({ createFromJob: () => of({ id: 'app-9' }) });

    store.trackJob('job-1');

    expect(markTracked).toHaveBeenCalledWith('job-1');
    expect(store.isTracked('job-1')).toBe(true);
    expect(store.trackingJobId()).toBeNull();
    expect(navigate).toHaveBeenCalledWith(['/dashboard/applications', 'app-9']);
  });

  it('ignores a second track click while one is already in flight', () => {
    const pending = new Subject<{ id: string }>();
    const { store, createFromJob } = setup({ createFromJob: () => pending.asObservable() });

    store.trackJob('job-1');
    expect(store.isTracking('job-1')).toBe(true);
    store.trackJob('job-2');

    expect(createFromJob).toHaveBeenCalledTimes(1);
    expect(store.isTracking('job-2')).toBe(false);
  });

  it('treats an already-tracked job as success and falls back to the list', () => {
    const { store, navigate, markTracked } = setup({
      createFromJob: () => throwError(() => ({ status: 409 })),
    });

    store.trackJob('job-1');

    expect(markTracked).toHaveBeenCalledWith('job-1');
    expect(navigate).toHaveBeenCalledWith(['/dashboard/applications']);
    expect(store.error()).toBe('');
    expect(store.trackingJobId()).toBeNull();
  });

  it('surfaces a tracking failure and stays on the page', () => {
    const { store, navigate, markTracked } = setup({
      createFromJob: () => throwError(() => ({ status: 500, error: { detail: 'nope' } })),
    });

    store.trackJob('job-1');

    expect(store.error()).toBe('nope');
    expect(store.trackingJobId()).toBeNull();
    expect(markTracked).not.toHaveBeenCalled();
    expect(navigate).not.toHaveBeenCalled();
  });
});

describe('IngestionStore preference feedback', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it('dims a rejected job immediately and coalesces rapid feedback into one refetch', () => {
    const { store, queryJobs } = setup();
    store.init();
    store.loadJobs();

    store.recordFeedback('job-1', 'not_interested');
    store.recordFeedback('job-2', 'not_interested');

    expect(store.isDimmed('job-1')).toBe(true);
    expect(store.isDimmed('job-2')).toBe(true);
    expect(queryJobs).toHaveBeenCalledTimes(1);

    vi.advanceTimersByTime(environment.feedbackRefetchDebounceMs);

    expect(queryJobs).toHaveBeenCalledTimes(2);
  });

  it('refetches for positive feedback without dimming the row', () => {
    const { store, queryJobs } = setup();
    store.init();
    store.loadJobs();

    store.recordFeedback('job-1', 'thumbs_up');

    expect(store.isDimmed('job-1')).toBe(false);

    vi.advanceTimersByTime(environment.feedbackRefetchDebounceMs);

    expect(queryJobs).toHaveBeenCalledTimes(2);
  });

  it('clears the dimmed set once a reload brings back re-ranked rows', () => {
    const { store } = setup();
    store.init();
    store.loadJobs();
    store.recordFeedback('job-1', 'not_interested');
    expect(store.isDimmed('job-1')).toBe(true);

    store.loadJobs();

    expect(store.isDimmed('job-1')).toBe(false);
  });
});

describe('IngestionStore detail panel', () => {
  it('opens and closes the selected job', () => {
    const { store } = setup();
    const job = makeJob({ id: 'job-3' });

    store.openDetail(job);
    expect(store.selectedJob()?.id).toBe('job-3');

    store.closeDetail();
    expect(store.selectedJob()).toBeNull();
  });
});
