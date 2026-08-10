import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, Router } from '@angular/router';
import { Observable, Subject, of, throwError } from 'rxjs';
import { ApplicationsService } from '../../core/services/applications.service';
import { ResearchService } from '../../core/services/research.service';
import { TrackingService } from '../../core/services/tracking.service';
import { ApplicationListItem } from '@core/contracts/application-list-item.model';
import { BatchEvaluationResponse } from '@core/contracts/batch-evaluation-response.model';
import { BatchResult } from '@core/contracts/batch-result.model';
import { CompanyResearch } from '@core/contracts/company-research.model';
import { PagedResult } from '@core/contracts/paged-result.model';
import { TrackedApplication } from '@core/contracts/tracked-application.model';
import { ApplicationsStore } from './applications.store';

function makeItem(over: Partial<ApplicationListItem> = {}): ApplicationListItem {
  return {
    id: 'app-1',
    title: 'Senior Backend Engineer',
    company: 'Acme Corp',
    status: 'saved',
    url: null,
    created_at: '2026-01-01T00:00:00Z',
    has_match: false,
    has_optimization: false,
    has_prep: false,
    latest_match_score: 0.5,
    job_id: null,
    notes: null,
    applied_at: null,
    location: null,
    remote_modality: null,
    salary_range: null,
    source: null,
    posted_date: null,
    ...over,
  };
}

// `count` items with distinct, ascending created_at stamps so the default
// created-descending sort produces a deterministic order (app-N first).
function makeItems(count: number): ApplicationListItem[] {
  return Array.from({ length: count }, (_, i) =>
    makeItem({
      id: `app-${i}`,
      created_at: `2026-01-${String(i + 1).padStart(2, '0')}T00:00:00Z`,
    }),
  );
}

function makeTracked(over: Partial<TrackedApplication> = {}): TrackedApplication {
  return {
    id: 'app-1',
    job_id: null,
    title: 'Senior Backend Engineer',
    company: 'Acme Corp',
    url: null,
    status: 'applied',
    notes: null,
    applied_at: '2026-02-02T00:00:00Z',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-02-02T00:00:00Z',
    location: null,
    remote_modality: null,
    salary_range: null,
    source: null,
    posted_date: null,
    ...over,
  };
}

function makeResearch(over: Partial<CompanyResearch> = {}): CompanyResearch {
  return {
    id: 'r-1',
    company_name: 'Acme Corp',
    funding_stage: 'Series B',
    tech_stack: 'Python, Postgres',
    culture_summary: 'Great',
    growth_trajectory: 'Up',
    red_flags: null,
    pros: 'Many',
    cons: 'Few',
    industry: null,
    company_size: null,
    headquarters: null,
    website: null,
    description: null,
    logo_url: null,
    created_at: null,
    updated_at: null,
    ...over,
  };
}

function makeBatchResult(over: Partial<BatchResult> = {}): BatchResult {
  return {
    job_title: 'Senior Backend Engineer',
    company: 'Acme Corp',
    source: 'tracked',
    source_id: 'app-1',
    composite_score: 0.8,
    dimensions: [],
    failed: false,
    ...over,
  };
}

interface SetupOptions {
  readonly listAll?: () => Observable<PagedResult<ApplicationListItem>>;
  readonly remove?: () => Observable<void>;
  readonly update?: () => Observable<TrackedApplication>;
  readonly batchEvaluate?: () => Observable<BatchEvaluationResponse>;
  readonly research?: () => Observable<CompanyResearch>;
  readonly refresh?: () => Observable<CompanyResearch>;
}

function setup(over: SetupOptions = {}) {
  const listAll = vi.fn(
    over.listAll ??
      ((): Observable<PagedResult<ApplicationListItem>> => of({ items: [makeItem()], total: 1 })),
  );
  const remove = vi.fn(over.remove ?? ((): Observable<void> => of(undefined)));
  const update = vi.fn(over.update ?? ((): Observable<TrackedApplication> => of(makeTracked())));
  const batchEvaluate = vi.fn(
    over.batchEvaluate ??
      ((): Observable<BatchEvaluationResponse> =>
        of({ total_jobs: 1, results: [makeBatchResult()] })),
  );
  const research = vi.fn(over.research ?? (() => of(makeResearch())));
  const refresh = vi.fn(over.refresh ?? (() => of(makeResearch())));
  const navigate = vi.fn();
  const route = { snapshot: { queryParamMap: { has: () => false } } };

  TestBed.configureTestingModule({
    providers: [
      ApplicationsStore,
      { provide: ApplicationsService, useValue: { listAll, remove } },
      { provide: TrackingService, useValue: { update, batchEvaluate } },
      { provide: ResearchService, useValue: { research, refresh } },
      { provide: Router, useValue: { navigate } },
      { provide: ActivatedRoute, useValue: route },
    ],
  });

  return {
    store: TestBed.inject(ApplicationsStore),
    listAll,
    remove,
    update,
    batchEvaluate,
    research,
    refresh,
    navigate,
  };
}

describe('ApplicationsStore loading', () => {
  it('loads the list and reports no truncation when the walk covered everything', () => {
    const { store } = setup({ listAll: () => of({ items: makeItems(3), total: 3 }) });

    store.init();

    expect(store.applications().length).toBe(3);
    expect(store.truncatedAt()).toBeNull();
    expect(store.loading()).toBe(false);
    expect(store.error()).toBe('');
  });

  it('reports the server total when the walk stopped short of it', () => {
    const { store } = setup({ listAll: () => of({ items: makeItems(3), total: 2500 }) });

    store.init();

    expect(store.truncatedAt()).toBe(2500);
  });

  it('ignores a second init so the list is not fetched twice', () => {
    const { store, listAll } = setup();

    store.init();
    store.init();

    expect(listAll).toHaveBeenCalledTimes(1);
  });

  it('keeps the loaded rows and clears the spinner when a refresh fails', () => {
    const { store, listAll } = setup({ listAll: () => of({ items: makeItems(2), total: 2 }) });
    store.init();

    listAll.mockImplementation(() => throwError(() => ({ error: { detail: 'boom' } })));
    store.load();

    expect(store.error()).toBe('boom');
    expect(store.loading()).toBe(false);
    expect(store.applications().length).toBe(2);
  });

  it('falls back to a generic message when the load failure carries no detail', () => {
    const { store } = setup({ listAll: () => throwError(() => new Error('offline')) });

    store.init();

    expect(store.error()).toBe('Failed to load applications');
    expect(store.loading()).toBe(false);
  });
});

describe('ApplicationsStore search, sort and paging', () => {
  it('renders one page at a time over the filtered rows', () => {
    const { store } = setup({ listAll: () => of({ items: makeItems(25), total: 25 }) });
    store.init();

    expect(store.totalPages()).toBe(2);
    expect(store.visibleApplications().length).toBe(20);
    expect(store.visibleApplications()[0].id).toBe('app-24');

    store.goToPage(2);

    expect(store.visibleApplications().length).toBe(5);
    expect(store.visibleApplications()[0].id).toBe('app-4');
  });

  it('pulls the user back to the last page when a search strands them past it', () => {
    const { store } = setup({
      listAll: () =>
        of({
          items: [...makeItems(24), makeItem({ id: 'needle', title: 'Unique Role' })],
          total: 25,
        }),
    });
    store.init();
    store.goToPage(2);
    expect(store.currentPage()).toBe(2);

    // Set the signal directly: setQuery() resets the page itself, and the point
    // here is that the clamp holds even when the page is left stale.
    store.query.set('unique');

    expect(store.totalPages()).toBe(1);
    expect(store.currentPage()).toBe(1);
    expect(store.visibleApplications().map((a) => a.id)).toEqual(['needle']);
  });

  it('returns to the first page whenever the result set changes shape', () => {
    const { store } = setup({ listAll: () => of({ items: makeItems(25), total: 25 }) });
    store.init();

    store.goToPage(2);
    store.setQuery('senior');
    expect(store.page()).toBe(1);

    store.goToPage(2);
    store.selectStatus('applied');
    expect(store.page()).toBe(1);

    store.selectStatus('');
    store.goToPage(2);
    store.setPageSize(5);
    expect(store.page()).toBe(1);
    expect(store.visibleApplications().length).toBe(5);
  });

  it('sorts unscored applications to the bottom in both directions', () => {
    const { store } = setup({
      listAll: () =>
        of({
          items: [
            makeItem({ id: 'low', latest_match_score: 0.2 }),
            makeItem({ id: 'unscored', latest_match_score: null }),
            makeItem({ id: 'high', latest_match_score: 0.9 }),
          ],
          total: 3,
        }),
    });
    store.init();

    store.sort.toggle('match'); // non-text column → descending first
    expect(store.visibleApplications().map((a) => a.id)).toEqual(['high', 'low', 'unscored']);

    store.sort.toggle('match'); // same column → flips direction
    expect(store.visibleApplications().map((a) => a.id)).toEqual(['low', 'high', 'unscored']);
  });

  it('searches across both the title and the company', () => {
    const { store } = setup({
      listAll: () =>
        of({
          items: [
            makeItem({ id: 'by-title', title: 'Rust Engineer', company: 'Acme Corp' }),
            makeItem({ id: 'by-company', title: 'Designer', company: 'Rustic Labs' }),
            makeItem({ id: 'neither', title: 'Designer', company: 'Globex' }),
          ],
          total: 3,
        }),
    });
    store.init();

    store.setQuery('rust');

    expect(
      store
        .visibleApplications()
        .map((a) => a.id)
        .sort(),
    ).toEqual(['by-company', 'by-title']);
  });
});

describe('ApplicationsStore row mutations', () => {
  afterEach(() => vi.restoreAllMocks());

  it('merges the new status and applied date into the row', () => {
    const onFailure = vi.fn();
    const { store, update } = setup();
    store.init();

    store.updateStatus(store.applications()[0], 'applied', onFailure);

    expect(update).toHaveBeenCalledWith('app-1', { status: 'applied' });
    expect(store.applications()[0].status).toBe('applied');
    expect(store.applications()[0].applied_at).toBe('2026-02-02T00:00:00Z');
    expect(onFailure).not.toHaveBeenCalled();
  });

  it('asks the view to revert the select when the status update fails', () => {
    const onFailure = vi.fn();
    const { store } = setup({
      update: () => throwError(() => ({ error: { detail: 'status boom' } })),
    });
    store.init();

    store.updateStatus(store.applications()[0], 'applied', onFailure);

    expect(onFailure).toHaveBeenCalledTimes(1);
    expect(store.error()).toBe('status boom');
    expect(store.applications()[0].status).toBe('saved');
  });

  it('marks the row as deleting only while the request is in flight', () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    const pending = new Subject<void>();
    const { store } = setup({ remove: () => pending.asObservable() });
    store.init();

    store.remove(store.applications()[0]);
    expect(store.deletingId()).toBe('app-1');
    expect(store.applications().length).toBe(1);

    pending.next(undefined);

    expect(store.deletingId()).toBeNull();
    expect(store.applications()).toEqual([]);
  });

  it('leaves the row alone when the delete confirmation is declined', () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false);
    const { store, remove } = setup();
    store.init();

    store.remove(store.applications()[0]);

    expect(remove).not.toHaveBeenCalled();
    expect(store.applications().length).toBe(1);
    expect(store.deletingId()).toBeNull();
  });
});

describe('ApplicationsStore batch evaluation', () => {
  it('drops the previous run before starting a new one', () => {
    const { store, batchEvaluate } = setup({
      batchEvaluate: () => throwError(() => ({ error: { detail: 'evaluate boom' } })),
    });
    store.init();

    store.evaluateAll();
    expect(store.error()).toBe('evaluate boom');
    expect(store.leaderboard()).toEqual([]);

    batchEvaluate.mockImplementation(() =>
      of({ total_jobs: 1, results: [makeBatchResult({ source_id: 'app-1' })] }),
    );
    store.evaluateAll();

    expect(store.error()).toBe('');
    expect(store.leaderboard().length).toBe(1);
    expect(store.evaluating()).toBe(false);
  });

  it('shows the manual error rather than a stale evaluation error', () => {
    const { store, listAll } = setup({
      batchEvaluate: () => throwError(() => ({ error: { detail: 'evaluate boom' } })),
    });
    store.init();
    store.evaluateAll();

    listAll.mockImplementation(() => throwError(() => ({ error: { detail: 'list boom' } })));
    store.load();

    expect(store.error()).toBe('list boom');
  });

  it('collapses an expanded breakdown when the same row is toggled again', () => {
    const { store } = setup();

    store.toggleExpand('app-1');
    expect(store.expandedResultId()).toBe('app-1');

    store.toggleExpand('app-1');
    expect(store.expandedResultId()).toBeNull();

    store.toggleExpand('app-2');
    expect(store.expandedResultId()).toBe('app-2');
  });
});

describe('ApplicationsStore company research', () => {
  it('sends the stored notes as the job description and expands the result', () => {
    const { store, research } = setup({
      listAll: () => of({ items: [makeItem({ notes: 'Referred by Ada.' })], total: 1 }),
    });
    store.init();

    store.researchCompany(store.applications()[0]);

    expect(research).toHaveBeenCalledWith({
      company_name: 'Acme Corp',
      job_description: 'Referred by Ada.',
    });
    expect(store.hasResearch('app-1')).toBe(true);
    expect(store.expandedResearchId()).toBe('app-1');
    expect(store.researchingCompany()).toBeNull();
  });

  it('refreshes the cached research in place without expanding the card', () => {
    const { store, refresh } = setup({
      refresh: () => of(makeResearch({ funding_stage: 'Series C' })),
    });
    store.init();

    store.refreshResearch(store.applications()[0]);

    expect(refresh).toHaveBeenCalledWith({ company_name: 'Acme Corp', job_description: '' });
    expect(store.researchCache()['app-1'].funding_stage).toBe('Series C');
    expect(store.expandedResearchId()).toBeNull();
    expect(store.researchingCompany()).toBeNull();
  });

  it('clears the spinner and caches nothing when the research fails', () => {
    const { store } = setup({
      research: () => throwError(() => ({ error: { detail: 'research boom' } })),
    });
    store.init();

    store.researchCompany(store.applications()[0]);

    expect(store.error()).toBe('research boom');
    expect(store.hasResearch('app-1')).toBe(false);
    expect(store.researchingCompany()).toBeNull();
  });
});

describe('ApplicationsStore navigation', () => {
  it('opens the application behind a tracked leaderboard card', () => {
    const { store, navigate } = setup();

    store.openLeaderboardResult(makeBatchResult({ source: 'tracked', source_id: 'app-7' }));

    expect(navigate).toHaveBeenCalledWith(['/dashboard/applications', 'app-7']);
  });

  it('ignores a leaderboard card that is not a tracked application', () => {
    const { store, navigate } = setup();

    store.openLeaderboardResult(makeBatchResult({ source: 'ingested', source_id: 'job-7' }));

    expect(navigate).not.toHaveBeenCalled();
  });

  it('closes the create dialog and opens the new application', () => {
    const { store, navigate } = setup();
    store.openCreate();
    expect(store.showCreateDialog()).toBe(true);

    store.onCreated('app-9');

    expect(store.showCreateDialog()).toBe(false);
    expect(navigate).toHaveBeenCalledWith(['/dashboard/applications', 'app-9']);
  });
});
