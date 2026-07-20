import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, Router, provideRouter } from '@angular/router';
import { Subject, of, throwError } from 'rxjs';
import { ApplicationsComponent } from './applications.component';
import { ApplicationsService } from '../../core/services/applications.service';
import { TrackingService } from '../../core/services/tracking.service';
import { ResearchService } from '../../core/services/research.service';
import { ApplicationListItem } from './models/application-list-item.model';
import { CompanyResearch } from '../tracking/models/company-research.model';

function makeItem(over: Partial<ApplicationListItem> = {}): ApplicationListItem {
  return {
    id: 'app-1',
    title: 'Senior Backend Engineer',
    company: 'Acme Corp',
    status: 'saved',
    url: 'https://example.com/job-1',
    created_at: '2026-01-01T00:00:00Z',
    has_match: true,
    has_optimization: false,
    has_prep: false,
    latest_match_score: 0.82,
    job_id: null,
    notes: null,
    applied_at: null,
    location: 'Remote',
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

describe('ApplicationsComponent', () => {
  function mount(
    opts: {
      list?: () => unknown;
      remove?: () => unknown;
      update?: () => unknown;
      batchEvaluate?: () => unknown;
      research?: () => unknown;
      refresh?: () => unknown;
    } = {},
  ) {
    const list = vi.fn(opts.list ?? (() => of([makeItem()])));
    const remove = vi.fn(opts.remove ?? (() => of(undefined)));
    const update = vi.fn(opts.update ?? ((id: string) => of(makeItem({ id, status: 'applied' }))));
    const batchEvaluate = vi.fn(opts.batchEvaluate ?? (() => of({ total_jobs: 1, results: [] })));
    const research = vi.fn(opts.research ?? (() => of(makeResearch())));
    const refresh = vi.fn(opts.refresh ?? (() => of(makeResearch())));

    TestBed.configureTestingModule({
      imports: [ApplicationsComponent],
      providers: [
        provideRouter([]),
        { provide: ApplicationsService, useValue: { list, remove } },
        { provide: TrackingService, useValue: { update, batchEvaluate } },
        { provide: ResearchService, useValue: { research, refresh } },
      ],
    });
    const navigate = vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);
    const fixture = TestBed.createComponent(ApplicationsComponent);
    fixture.detectChanges();
    return { fixture, list, remove, update, batchEvaluate, research, refresh, navigate };
  }

  it('loads and renders a row per application', () => {
    const { fixture, list } = mount({ list: () => of([makeItem(), makeItem({ id: 'app-2' })]) });
    expect(list).toHaveBeenCalled();
    expect(fixture.componentInstance.applications().length).toBe(2);
    const rows = fixture.nativeElement.querySelectorAll('tr.row');
    expect(rows.length).toBe(2);
  });

  it('renders the empty state when there are no applications', () => {
    const { fixture } = mount({ list: () => of([]) });
    expect(fixture.nativeElement.querySelector('.empty-state')).not.toBeNull();
    expect(fixture.nativeElement.querySelector('table.apps-table')).toBeNull();
  });

  it('shows an error alert when loading fails', () => {
    const { fixture } = mount({
      list: () => throwError(() => ({ error: { detail: 'boom' } })),
    });
    expect(fixture.componentInstance.error()).toBe('boom');
    expect(fixture.componentInstance.loading()).toBe(false);
    const alert = fixture.nativeElement.querySelector('.alert-error');
    expect(alert).not.toBeNull();
    expect(alert.textContent).toContain('boom');
  });

  it('falls back to a default error message when detail is missing', () => {
    const { fixture } = mount({ list: () => throwError(() => ({})) });
    expect(fixture.componentInstance.error()).toBe('Failed to load applications');
  });

  it('navigates to the detail page on open', () => {
    const { fixture, navigate } = mount();
    fixture.componentInstance.open('app-1');
    expect(navigate).toHaveBeenCalledWith(['/dashboard/applications', 'app-1']);
  });

  it('opens the create dialog via openCreate', () => {
    const { fixture } = mount();
    expect(fixture.componentInstance.showCreateDialog()).toBe(false);
    fixture.componentInstance.openCreate();
    expect(fixture.componentInstance.showCreateDialog()).toBe(true);
  });

  it('navigates and closes the dialog when a new application is created', () => {
    const { fixture, navigate } = mount();
    fixture.componentInstance.openCreate();
    fixture.componentInstance.onCreated('app-9');
    expect(fixture.componentInstance.showCreateDialog()).toBe(false);
    expect(navigate).toHaveBeenCalledWith(['/dashboard/applications', 'app-9']);
  });

  it('removes an application from the list on confirmed delete', () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    const item = makeItem();
    const { fixture, remove } = mount({ list: () => of([item]) });
    const event = { stopPropagation: vi.fn() } as unknown as MouseEvent;
    fixture.componentInstance.remove(item, event);
    expect(event.stopPropagation).toHaveBeenCalled();
    expect(remove).toHaveBeenCalledWith('app-1');
    expect(fixture.componentInstance.applications().length).toBe(0);
    expect(fixture.componentInstance.deletingId()).toBeNull();
  });

  it('does not call remove when delete is cancelled', () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false);
    const item = makeItem();
    const { fixture, remove } = mount({ list: () => of([item]) });
    const event = { stopPropagation: vi.fn() } as unknown as MouseEvent;
    fixture.componentInstance.remove(item, event);
    expect(remove).not.toHaveBeenCalled();
    expect(fixture.componentInstance.applications().length).toBe(1);
  });

  it('surfaces an error and keeps the row when delete fails', () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    const item = makeItem();
    const { fixture } = mount({
      list: () => of([item]),
      remove: () => throwError(() => ({ error: { detail: 'nope' } })),
    });
    const event = { stopPropagation: vi.fn() } as unknown as MouseEvent;
    fixture.componentInstance.remove(item, event);
    expect(fixture.componentInstance.error()).toBe('nope');
    expect(fixture.componentInstance.applications().length).toBe(1);
    expect(fixture.componentInstance.deletingId()).toBeNull();
  });

  it('shows a dismissible notice and strips the flag when redirected with notFound', () => {
    const navigate = vi.fn();
    const route = {
      snapshot: { queryParamMap: { has: (k: string) => k === 'notFound' } },
    };
    TestBed.configureTestingModule({
      imports: [ApplicationsComponent],
      providers: [
        { provide: Router, useValue: { navigate } },
        { provide: ActivatedRoute, useValue: route },
        { provide: ApplicationsService, useValue: { list: () => of([]), remove: vi.fn() } },
        { provide: TrackingService, useValue: { update: vi.fn(), batchEvaluate: vi.fn() } },
        { provide: ResearchService, useValue: { research: vi.fn(), refresh: vi.fn() } },
      ],
    });
    const fixture = TestBed.createComponent(ApplicationsComponent);
    fixture.detectChanges();

    expect(fixture.componentInstance.notice()).toContain('no longer exists');
    expect(fixture.nativeElement.querySelector('.notice-banner')).not.toBeNull();
    // The flag is stripped so a refresh doesn't re-show the notice.
    expect(navigate).toHaveBeenCalledWith(
      [],
      expect.objectContaining({ queryParams: {}, replaceUrl: true }),
    );

    fixture.componentInstance.dismissNotice();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.notice-banner')).toBeNull();
  });
});

describe('ApplicationsComponent status tabs / filtering', () => {
  function mountWith(rows: ApplicationListItem[]): ApplicationsComponent {
    TestBed.configureTestingModule({
      imports: [ApplicationsComponent],
      providers: [
        provideRouter([]),
        {
          provide: ApplicationsService,
          useValue: { list: () => of(rows), remove: () => of(undefined) },
        },
        {
          provide: TrackingService,
          useValue: { update: () => of(rows[0]), batchEvaluate: () => of({ results: [] }) },
        },
        {
          provide: ResearchService,
          useValue: { research: () => of(makeResearch()), refresh: () => of(makeResearch()) },
        },
      ],
    });
    const fixture = TestBed.createComponent(ApplicationsComponent);
    fixture.detectChanges();
    return fixture.componentInstance;
  }

  it('defaults to created descending', () => {
    const comp = mountWith([
      makeItem({ id: 'a', created_at: '2026-01-01T00:00:00Z' }),
      makeItem({ id: 'b', created_at: '2026-05-01T00:00:00Z' }),
      makeItem({ id: 'c', created_at: '2026-03-01T00:00:00Z' }),
    ]);
    expect(comp.visibleApplications().map((a) => a.id)).toEqual(['b', 'c', 'a']);
  });

  it('filters by query across title and company', () => {
    const comp = mountWith([
      makeItem({ id: 'a', title: 'Engineer', company: 'Globex' }),
      makeItem({ id: 'b', title: 'Designer', company: 'Acme' }),
    ]);
    comp.query.set('acme');
    expect(comp.visibleApplications().map((a) => a.id)).toEqual(['b']);
  });

  it('sorts by status ascending when toggled', () => {
    const comp = mountWith([
      makeItem({ id: 'a', status: 'saved' }),
      makeItem({ id: 'b', status: 'applied' }),
    ]);
    comp.sort.toggle('status'); // text field default asc; "applied" < "saved"
    expect(comp.visibleApplications().map((a) => a.id)).toEqual(['b', 'a']);
  });

  it('filters the list by the selected status tab', () => {
    const comp = mountWith([
      makeItem({ id: 'a', status: 'saved' }),
      makeItem({ id: 'b', status: 'applied' }),
      makeItem({ id: 'c', status: 'applied' }),
    ]);
    comp.selectStatus('applied');
    expect(
      comp
        .visibleApplications()
        .map((a) => a.id)
        .sort(),
    ).toEqual(['b', 'c']);
  });

  it('counts applications per status tab (All is the total)', () => {
    const comp = mountWith([
      makeItem({ id: 'a', status: 'saved' }),
      makeItem({ id: 'b', status: 'applied' }),
      makeItem({ id: 'c', status: 'applied' }),
    ]);
    expect(comp.statusCount('')).toBe(3);
    expect(comp.statusCount('applied')).toBe(2);
    expect(comp.statusCount('saved')).toBe(1);
    expect(comp.statusCount('rejected')).toBe(0);
  });

  it('excludes the active status filter from the tab counts but applies the search', () => {
    const comp = mountWith([
      makeItem({ id: 'a', status: 'saved', company: 'Acme' }),
      makeItem({ id: 'b', status: 'applied', company: 'Globex' }),
    ]);
    comp.selectStatus('applied');
    comp.query.set('acme');
    // Search narrows to the 'saved/Acme' row; counts reflect search, not the tab filter.
    expect(comp.statusCount('saved')).toBe(1);
    expect(comp.statusCount('applied')).toBe(0);
  });
});

describe('ApplicationsComponent merged pipeline capabilities', () => {
  function mount(
    opts: {
      list?: () => unknown;
      update?: () => unknown;
      batchEvaluate?: () => unknown;
      research?: () => unknown;
    } = {},
  ) {
    const list = vi.fn(opts.list ?? (() => of([makeItem()])));
    const update = vi.fn(opts.update ?? (() => of(makeItem({ status: 'applied' }))));
    const batchEvaluate = vi.fn(opts.batchEvaluate ?? (() => of({ total_jobs: 1, results: [] })));
    const research = vi.fn(opts.research ?? (() => of(makeResearch())));

    TestBed.configureTestingModule({
      imports: [ApplicationsComponent],
      providers: [
        provideRouter([]),
        { provide: ApplicationsService, useValue: { list, remove: () => of(undefined) } },
        { provide: TrackingService, useValue: { update, batchEvaluate } },
        { provide: ResearchService, useValue: { research, refresh: () => of(makeResearch()) } },
      ],
    });
    const navigate = vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);
    const fixture = TestBed.createComponent(ApplicationsComponent);
    fixture.detectChanges();
    return { fixture, list, update, batchEvaluate, research, navigate };
  }

  it('updates status inline via the tracking service and reflects it in the row', () => {
    const item = makeItem();
    const update = vi.fn(() => of(makeItem({ status: 'applied' })));
    const { fixture } = mount({ list: () => of([item]), update });
    const select = { value: 'applied' } as HTMLSelectElement;
    fixture.componentInstance.updateStatus(item, { target: select } as unknown as Event);
    expect(update).toHaveBeenCalledWith('app-1', { status: 'applied' });
    expect(fixture.componentInstance.applications()[0].status).toBe('applied');
  });

  it('reverts the select and shows an error when status update fails', () => {
    const item = makeItem();
    const { fixture } = mount({
      list: () => of([item]),
      update: () => throwError(() => ({ error: { detail: 'status boom' } })),
    });
    const select = { value: 'applied' } as HTMLSelectElement;
    fixture.componentInstance.updateStatus(item, { target: select } as unknown as Event);
    expect(fixture.componentInstance.error()).toBe('status boom');
    expect(select.value).toBe('saved');
  });

  it('populates the leaderboard via batch evaluation using application ids', () => {
    const item = makeItem();
    const batchEvaluate = vi.fn(() =>
      of({
        total_jobs: 1,
        results: [
          {
            job_title: 'Eng',
            company: 'Acme',
            source: 'tracked',
            source_id: 'app-1',
            composite_score: 0.8,
            dimensions: [],
            failed: false,
          },
        ],
      }),
    );
    const { fixture } = mount({ list: () => of([item]), batchEvaluate });
    fixture.componentInstance.evaluateAll();
    expect(batchEvaluate).toHaveBeenCalledWith(['app-1']);
    expect(fixture.componentInstance.leaderboard().length).toBe(1);
    expect(fixture.componentInstance.evaluating()).toBe(false);
  });

  it('does not evaluate when there are no applications', () => {
    const { fixture, batchEvaluate } = mount({ list: () => of([]) });
    fixture.componentInstance.evaluateAll();
    expect(batchEvaluate).not.toHaveBeenCalled();
  });

  it('keeps the leaderboard readable from a fresh component instance after the original is destroyed mid-run (survives navigation)', () => {
    const item = makeItem();
    const subject = new Subject<{ total_jobs: number; results: unknown[] }>();

    TestBed.configureTestingModule({
      imports: [ApplicationsComponent],
      providers: [
        provideRouter([]),
        {
          provide: ApplicationsService,
          useValue: { list: () => of([item]), remove: () => of(undefined) },
        },
        {
          provide: TrackingService,
          useValue: { update: () => of(item), batchEvaluate: () => subject.asObservable() },
        },
        { provide: ResearchService, useValue: { research: () => of(makeResearch()) } },
      ],
    });

    const first = TestBed.createComponent(ApplicationsComponent);
    first.detectChanges();
    first.componentInstance.evaluateAll();
    expect(first.componentInstance.evaluating()).toBe(true);

    // Simulate navigating away mid-request.
    first.destroy();

    subject.next({
      total_jobs: 1,
      results: [
        {
          job_title: 'Eng',
          company: 'Acme',
          source: 'tracked',
          source_id: 'app-1',
          composite_score: 0.8,
          dimensions: [],
          failed: false,
        },
      ],
    });
    subject.complete();

    // A freshly mounted instance reads the cached leaderboard without
    // re-triggering evaluateAll().
    const second = TestBed.createComponent(ApplicationsComponent);
    second.detectChanges();
    expect(second.componentInstance.evaluating()).toBe(false);
    expect(second.componentInstance.leaderboard().length).toBe(1);
  });

  it('navigates to the application detail when a tracked leaderboard card is opened', () => {
    const { fixture, navigate } = mount();
    fixture.componentInstance.openLeaderboardResult({
      job_title: 'Eng',
      company: 'Acme',
      source: 'tracked',
      source_id: 'app-1',
      composite_score: 0.8,
      dimensions: [],
      failed: false,
    });
    expect(navigate).toHaveBeenCalledWith(['/dashboard/applications', 'app-1']);
  });

  it('researches a company and caches the result, expanding it', () => {
    const item = makeItem();
    const research = vi.fn(() => of(makeResearch()));
    const { fixture } = mount({ list: () => of([item]), research });
    const event = { stopPropagation: vi.fn() } as unknown as Event;
    fixture.componentInstance.researchCompany(item, event);
    expect(research).toHaveBeenCalledWith({ company_name: 'Acme Corp', job_description: '' });
    expect(fixture.componentInstance.hasResearch('app-1')).toBe(true);
    expect(fixture.componentInstance.expandedResearchId()).toBe('app-1');
    expect(fixture.componentInstance.researchingCompany()).toBeNull();
  });

  it('toggles a leaderboard breakdown without triggering navigation', () => {
    const { fixture, navigate } = mount();
    const event = { stopPropagation: vi.fn() } as unknown as Event;
    fixture.componentInstance.toggleExpand('app-1', event);
    expect(event.stopPropagation).toHaveBeenCalled();
    expect(fixture.componentInstance.expandedResultId()).toBe('app-1');
    expect(navigate).not.toHaveBeenCalled();
  });
});
