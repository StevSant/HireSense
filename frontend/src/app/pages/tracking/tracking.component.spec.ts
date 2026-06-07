import { TestBed } from '@angular/core/testing';
import { of, throwError } from 'rxjs';
import { TrackingComponent } from './tracking.component';
import { TrackingService } from '../../core/services/tracking.service';
import { ResearchService } from '../../core/services/research.service';
import { TrackedApplication } from './models/tracked-application.model';
import { CompanyResearch } from './models/company-research.model';

function makeApp(over: Partial<TrackedApplication> = {}): TrackedApplication {
  return {
    id: 'app-1',
    job_id: null,
    title: 'Senior Backend Engineer',
    company: 'Acme Corp',
    url: 'https://example.com/job-1',
    status: 'saved',
    notes: null,
    applied_at: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
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
    created_at: null,
    updated_at: null,
    ...over,
  };
}

describe('TrackingComponent', () => {
  function mount(opts: {
    list?: () => unknown;
    create?: () => unknown;
    update?: () => unknown;
    deleteFn?: () => unknown;
    batchEvaluate?: () => unknown;
    research?: () => unknown;
    refresh?: () => unknown;
  } = {}) {
    const list = vi.fn(opts.list ?? (() => of([makeApp()])));
    const create = vi.fn(opts.create ?? (() => of(makeApp({ id: 'new-app' }))));
    const update = vi.fn(opts.update ?? ((id: string) => of(makeApp({ id, status: 'applied' }))));
    const deleteFn = vi.fn(opts.deleteFn ?? (() => of(undefined)));
    const batchEvaluate = vi.fn(opts.batchEvaluate ?? (() => of({ total_jobs: 1, results: [] })));
    const research = vi.fn(opts.research ?? (() => of(makeResearch())));
    const refresh = vi.fn(opts.refresh ?? (() => of(makeResearch())));

    TestBed.configureTestingModule({
      imports: [TrackingComponent],
      providers: [
        { provide: TrackingService, useValue: { list, create, update, delete: deleteFn, batchEvaluate } },
        { provide: ResearchService, useValue: { research, refresh } },
      ],
    });
    const fixture = TestBed.createComponent(TrackingComponent);
    fixture.detectChanges();
    return { fixture, list, create, update, deleteFn, batchEvaluate, research, refresh };
  }

  it('loads and renders a row per tracked application', () => {
    const { fixture, list } = mount({ list: () => of([makeApp(), makeApp({ id: 'app-2' })]) });
    expect(list).toHaveBeenCalledWith(undefined);
    expect(fixture.componentInstance.applications().length).toBe(2);
    expect(fixture.nativeElement.querySelectorAll('tbody tr').length).toBe(2);
  });

  it('renders the empty state when there are no applications', () => {
    const { fixture } = mount({ list: () => of([]) });
    expect(fixture.nativeElement.querySelector('.empty-state')).not.toBeNull();
    expect(fixture.nativeElement.querySelector('table')).toBeNull();
  });

  it('shows an error alert when loading fails', () => {
    const { fixture } = mount({ list: () => throwError(() => ({ error: { detail: 'load boom' } })) });
    expect(fixture.componentInstance.error()).toBe('load boom');
    expect(fixture.componentInstance.loading()).toBe(false);
    expect(fixture.nativeElement.querySelector('.alert-error').textContent).toContain('load boom');
  });

  it('reloads with the chosen status filter', () => {
    const { fixture, list } = mount();
    list.mockClear();
    fixture.componentInstance.onStatusFilterChange({ target: { value: 'applied' } } as unknown as Event);
    expect(fixture.componentInstance.statusFilter()).toBe('applied');
    expect(list).toHaveBeenCalledWith('applied');
  });

  it('adds an application and prepends it to the list', () => {
    const created = makeApp({ id: 'new-app', title: 'New Role', company: 'NewCo' });
    const { fixture, create } = mount({ create: () => of(created) });
    fixture.componentInstance.newTitle.set('New Role');
    fixture.componentInstance.newCompany.set('NewCo');
    fixture.componentInstance.addApplication();
    expect(create).toHaveBeenCalledWith({ title: 'New Role', company: 'NewCo' });
    expect(fixture.componentInstance.applications()[0].id).toBe('new-app');
    expect(fixture.componentInstance.adding()).toBe(false);
    expect(fixture.componentInstance.showAddForm()).toBe(false);
  });

  it('does not add when both title and company are empty', () => {
    const { fixture, create } = mount();
    fixture.componentInstance.addApplication();
    expect(create).not.toHaveBeenCalled();
  });

  it('surfaces an error when add fails', () => {
    const { fixture } = mount({ create: () => throwError(() => ({ error: { detail: 'add boom' } })) });
    fixture.componentInstance.newTitle.set('X');
    fixture.componentInstance.addApplication();
    expect(fixture.componentInstance.error()).toBe('add boom');
    expect(fixture.componentInstance.adding()).toBe(false);
  });

  it('updates the status and replaces the row in place', () => {
    const app = makeApp();
    const update = vi.fn(() => of(makeApp({ status: 'applied' })));
    const { fixture } = mount({ list: () => of([app]), update });
    const select = { value: 'applied' } as HTMLSelectElement;
    fixture.componentInstance.updateStatus(app, { target: select } as unknown as Event);
    expect(update).toHaveBeenCalledWith('app-1', { status: 'applied' });
    expect(fixture.componentInstance.applications()[0].status).toBe('applied');
  });

  it('reverts the select and shows an error when status update fails', () => {
    const app = makeApp();
    const { fixture } = mount({
      list: () => of([app]),
      update: () => throwError(() => ({ error: { detail: 'status boom' } })),
    });
    const select = { value: 'applied' } as HTMLSelectElement;
    fixture.componentInstance.updateStatus(app, { target: select } as unknown as Event);
    expect(fixture.componentInstance.error()).toBe('status boom');
    expect(select.value).toBe('saved');
  });

  it('deletes an application and removes it from the list', () => {
    const app = makeApp();
    const deleteFn = vi.fn(() => of(undefined));
    const { fixture } = mount({ list: () => of([app]), deleteFn });
    fixture.componentInstance.deleteApplication('app-1');
    expect(deleteFn).toHaveBeenCalledWith('app-1');
    expect(fixture.componentInstance.applications().length).toBe(0);
  });

  it('surfaces an error when delete fails', () => {
    const app = makeApp();
    const { fixture } = mount({
      list: () => of([app]),
      deleteFn: () => throwError(() => ({ error: { detail: 'del boom' } })),
    });
    fixture.componentInstance.deleteApplication('app-1');
    expect(fixture.componentInstance.error()).toBe('del boom');
    expect(fixture.componentInstance.applications().length).toBe(1);
  });

  it('populates the leaderboard via batch evaluation', () => {
    const app = makeApp();
    const batchEvaluate = vi.fn(() =>
      of({
        total_jobs: 1,
        results: [
          { job_title: 'Eng', company: 'Acme', source: 'manual', source_id: 's1', composite_score: 0.8, dimensions: [], failed: false },
        ],
      }),
    );
    const { fixture } = mount({ list: () => of([app]), batchEvaluate });
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

  it('surfaces an error when batch evaluation fails', () => {
    const { fixture } = mount({
      list: () => of([makeApp()]),
      batchEvaluate: () => throwError(() => ({ error: { detail: 'eval boom' } })),
    });
    fixture.componentInstance.evaluateAll();
    expect(fixture.componentInstance.error()).toBe('eval boom');
    expect(fixture.componentInstance.evaluating()).toBe(false);
  });

  it('researches a company and caches the result, expanding it', () => {
    const app = makeApp();
    const research = vi.fn(() => of(makeResearch()));
    const { fixture } = mount({ list: () => of([app]), research });
    fixture.componentInstance.researchCompany(app);
    expect(research).toHaveBeenCalledWith({ company_name: 'Acme Corp', job_description: '' });
    expect(fixture.componentInstance.hasResearch('app-1')).toBe(true);
    expect(fixture.componentInstance.expandedResearchId()).toBe('app-1');
    expect(fixture.componentInstance.researchingCompany()).toBeNull();
  });

  it('surfaces an error when research fails', () => {
    const app = makeApp();
    const { fixture } = mount({
      list: () => of([app]),
      research: () => throwError(() => ({ error: { detail: 'research boom' } })),
    });
    fixture.componentInstance.researchCompany(app);
    expect(fixture.componentInstance.error()).toBe('research boom');
    expect(fixture.componentInstance.researchingCompany()).toBeNull();
  });

  it('toggles the add form and resets fields when collapsing', () => {
    const { fixture } = mount();
    fixture.componentInstance.toggleAddForm();
    expect(fixture.componentInstance.showAddForm()).toBe(true);
    fixture.componentInstance.newTitle.set('typed');
    fixture.componentInstance.toggleAddForm();
    expect(fixture.componentInstance.showAddForm()).toBe(false);
    expect(fixture.componentInstance.newTitle()).toBe('');
  });

  it('toggles research expansion', () => {
    const { fixture } = mount();
    fixture.componentInstance.toggleResearch('app-1');
    expect(fixture.componentInstance.expandedResearchId()).toBe('app-1');
    fixture.componentInstance.toggleResearch('app-1');
    expect(fixture.componentInstance.expandedResearchId()).toBeNull();
  });
});
