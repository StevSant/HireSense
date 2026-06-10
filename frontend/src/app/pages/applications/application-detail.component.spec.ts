import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, Router } from '@angular/router';
import { Subject, of, throwError } from 'rxjs';
import { signal } from '@angular/core';
import { ApplicationDetailComponent } from './application-detail.component';
import { ApplicationsService } from '../../core/services/applications.service';
import { CvOptimizationRunnerService } from '../../core/services/cv-optimization-runner.service';
import { CoverLetterRunnerService } from '../../core/services/cover-letter-runner.service';
import { PortfolioService } from '../../core/services/portfolio.service';
import { ApplicationAggregate } from './models/application-aggregate.model';
import { PortfolioEngagementResponse } from '../profile/models/portfolio-engagement.model';

function makeAggregate(over: Partial<ApplicationAggregate> = {}): ApplicationAggregate {
  return {
    id: 'app-1',
    job_id: 'job-1',
    title: 'Senior Backend Engineer',
    company: 'Acme Corp',
    url: 'https://example.com/job-1',
    status: 'saved',
    notes: null,
    applied_at: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    job_snapshot: {
      id: 'snap-1',
      description: 'Build great APIs.',
      required_skills: ['python'],
      source: 'manual',
      updated_at: null,
    },
    latest_match: null,
    latest_optimization: null,
    latest_interview_prep: null,
    latest_cover_letter: null,
    match_count: 0,
    optimization_count: 0,
    interview_prep_count: 0,
    cover_letter_count: 0,
    ...over,
  };
}

describe('ApplicationDetailComponent', () => {
  function mount(opts: {
    id?: string | null;
    tab?: string | null;
    get?: () => unknown;
    remove?: () => unknown;
    navigate?: ReturnType<typeof vi.fn>;
    optCompleted$?: Subject<string>;
    clCompleted$?: Subject<string>;
    engagement?: () => unknown;
  } = {}) {
    const get = vi.fn(opts.get ?? (() => of(makeAggregate())));
    const remove = vi.fn(opts.remove ?? (() => of(undefined)));
    const navigate = opts.navigate ?? vi.fn();
    const optCompleted$ = opts.optCompleted$ ?? new Subject<string>();
    const clCompleted$ = opts.clCompleted$ ?? new Subject<string>();
    const engagement = vi.fn(opts.engagement ?? (() => of({ configured: false, visits: [] } as PortfolioEngagementResponse)));

    const route = {
      snapshot: {
        paramMap: { get: () => (opts.id === undefined ? 'app-1' : opts.id) },
        queryParamMap: { get: () => opts.tab ?? null },
      },
    };

    const optRunner = {
      completed$: optCompleted$,
      isRunning: () => false,
      lastError: signal(''),
      run: vi.fn(),
    };
    const clRunner = {
      completed$: clCompleted$,
      isRunning: () => false,
      lastError: signal(''),
      run: vi.fn(),
    };

    TestBed.configureTestingModule({
      imports: [ApplicationDetailComponent],
      providers: [
        { provide: ActivatedRoute, useValue: route },
        { provide: Router, useValue: { navigate } },
        { provide: ApplicationsService, useValue: { get, remove } },
        { provide: CvOptimizationRunnerService, useValue: optRunner },
        { provide: CoverLetterRunnerService, useValue: clRunner },
        { provide: PortfolioService, useValue: { engagement, listProjects: vi.fn(), sync: vi.fn() } },
      ],
    });
    const fixture = TestBed.createComponent(ApplicationDetailComponent);
    fixture.detectChanges();
    return { fixture, get, remove, navigate, optCompleted$, clCompleted$, engagement };
  }

  it('loads the aggregate on init and renders the header', () => {
    const { fixture, get } = mount();
    expect(get).toHaveBeenCalledWith('app-1');
    expect(fixture.componentInstance.aggregate()?.id).toBe('app-1');
    expect(fixture.componentInstance.loading()).toBe(false);
    expect(fixture.nativeElement.querySelector('h1').textContent).toContain('Senior Backend Engineer');
  });

  it('defaults to the job tab and renders it', () => {
    const { fixture } = mount();
    expect(fixture.componentInstance.activeTab()).toBe('job');
    expect(fixture.nativeElement.querySelector('app-job-tab')).not.toBeNull();
  });

  it('honors a valid tab query param on init', () => {
    const { fixture } = mount({ tab: 'cv' });
    expect(fixture.componentInstance.activeTab()).toBe('cv');
    expect(fixture.nativeElement.querySelector('app-cv-tab')).not.toBeNull();
  });

  it('ignores an unknown tab query param', () => {
    const { fixture } = mount({ tab: 'bogus' });
    expect(fixture.componentInstance.activeTab()).toBe('job');
  });

  it('switches tabs and updates the query param without reloading', () => {
    const { fixture, get, navigate } = mount();
    get.mockClear();
    fixture.componentInstance.setTab('apply');
    fixture.detectChanges();
    expect(fixture.componentInstance.activeTab()).toBe('apply');
    expect(fixture.nativeElement.querySelector('app-apply-tab')).not.toBeNull();
    expect(navigate).toHaveBeenCalledWith(
      [],
      expect.objectContaining({ queryParams: { tab: 'apply' }, queryParamsHandling: 'merge', replaceUrl: true }),
    );
    expect(get).not.toHaveBeenCalled();
  });

  it('redirects to the list when there is no id param', () => {
    const { fixture, get, navigate } = mount({ id: null });
    expect(get).not.toHaveBeenCalled();
    expect(navigate).toHaveBeenCalledWith(['/dashboard/applications']);
    expect(fixture.componentInstance.aggregate()).toBeNull();
  });

  it('shows an error and clears loading when the fetch fails', () => {
    const { fixture } = mount({ get: () => throwError(() => ({ error: { detail: 'no app' } })) });
    expect(fixture.componentInstance.error()).toBe('no app');
    expect(fixture.componentInstance.loading()).toBe(false);
    expect(fixture.nativeElement.querySelector('.alert-error').textContent).toContain('no app');
  });

  it('refetches the aggregate when a CV optimization run completes for this app', () => {
    const { get, optCompleted$ } = mount();
    get.mockClear();
    optCompleted$.next('app-1');
    expect(get).toHaveBeenCalledWith('app-1');
  });

  it('ignores completion events for a different application', () => {
    const { get, clCompleted$ } = mount();
    get.mockClear();
    clCompleted$.next('other-app');
    expect(get).not.toHaveBeenCalled();
  });

  it('reload re-fetches the current aggregate', () => {
    const { fixture, get } = mount();
    get.mockClear();
    fixture.componentInstance.reload();
    expect(get).toHaveBeenCalledWith('app-1');
  });

  it('navigates back to the list', () => {
    const { fixture, navigate } = mount();
    fixture.componentInstance.backToList();
    expect(navigate).toHaveBeenCalledWith(['/dashboard/applications']);
  });

  it('deletes and navigates away on confirmed remove', () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    const { fixture, remove, navigate } = mount();
    fixture.componentInstance.remove();
    expect(remove).toHaveBeenCalledWith('app-1');
    expect(navigate).toHaveBeenCalledWith(['/dashboard/applications']);
    expect(fixture.componentInstance.deleting()).toBe(false);
  });

  it('does not delete when remove is cancelled', () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false);
    const { fixture, remove } = mount();
    fixture.componentInstance.remove();
    expect(remove).not.toHaveBeenCalled();
  });

  it('surfaces an error when delete fails', () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    const { fixture } = mount({ remove: () => throwError(() => ({ error: { detail: 'cannot' } })) });
    fixture.componentInstance.remove();
    expect(fixture.componentInstance.error()).toBe('cannot');
    expect(fixture.componentInstance.deleting()).toBe(false);
  });

  it('shows the portfolio visit chip when a matching visit exists', () => {
    const visit = {
      ref: 'ref-1', application_id: 'app-1', first_seen: '2026-06-01T00:00:00Z',
      last_seen: '2026-06-09T00:00:00Z', page_views: 3, cv_downloads: 0,
      country: 'US', organization: 'Acme',
    };
    const { fixture } = mount({
      engagement: () => of({ configured: true, visits: [visit] } as PortfolioEngagementResponse),
    });
    fixture.detectChanges();
    const chip = fixture.nativeElement.querySelector('.portfolio-visit-chip');
    expect(chip).not.toBeNull();
    expect(chip.textContent).toContain('Portfolio visited — 3 page views');
  });

  it('hides the portfolio visit chip when visits list is empty', () => {
    const { fixture } = mount({
      engagement: () => of({ configured: true, visits: [] } as PortfolioEngagementResponse),
    });
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.portfolio-visit-chip')).toBeNull();
  });
});
