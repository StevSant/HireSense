import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, Router } from '@angular/router';
import { of, throwError } from 'rxjs';
import { OptimizationComponent } from './optimization.component';
import { ApplicationsService } from '../../core/services/applications.service';
import { IngestionService } from '../../core/services/ingestion.service';

function makeJob(over: Partial<Record<string, unknown>> = {}) {
  return {
    id: 'job-1',
    title: 'Senior Backend Engineer',
    company: 'Acme Corp',
    description: 'Build great APIs.',
    skills: [],
    location: 'Remote',
    salary_range: null,
    source: 'remotive',
    source_type: 'feed',
    platform: null,
    categories: [],
    department: null,
    url: 'https://example.com/job-1',
    posted_date: null,
    match_score: null,
    llm_score: null,
    verdict: null,
    reasons: [],
    dealbreakers: [],
    ...over,
  };
}

describe('OptimizationComponent', () => {
  function mount(opts: {
    jobId?: string | null;
    getJob?: () => unknown;
    applications?: Partial<Record<string, unknown>>;
  } = {}) {
    const route = {
      snapshot: {
        queryParamMap: { get: (key: string) => (key === 'job_id' ? opts.jobId ?? null : null) },
      },
    };
    const ingestion = {
      getJob: opts.getJob ?? (() => of(makeJob())),
    };
    const applications = {
      createManual: () => of({ id: 'app-1' }),
      ...opts.applications,
    };

    TestBed.configureTestingModule({
      imports: [OptimizationComponent],
      providers: [
        { provide: ActivatedRoute, useValue: route },
        { provide: IngestionService, useValue: ingestion },
        { provide: ApplicationsService, useValue: applications },
        { provide: Router, useValue: { navigate: () => {} } },
      ],
    });
    const fixture = TestBed.createComponent(OptimizationComponent);
    fixture.detectChanges();
    return fixture;
  }

  it('renders the manual form with no pre-fill when job_id is absent', () => {
    const fixture = mount();
    const cmp = fixture.componentInstance;

    expect(cmp.prefilledFromJob()).toBe(false);
    expect(cmp.title()).toBe('');
    expect(cmp.company()).toBe('');
    expect(fixture.nativeElement.querySelector('.job-context')).toBeNull();
  });

  it('pre-fills title/company/description from the job when job_id is present', () => {
    const getJob = vi.fn(() => of(makeJob()));
    const fixture = mount({ jobId: 'job-1', getJob });
    const cmp = fixture.componentInstance;

    expect(getJob).toHaveBeenCalledWith('job-1');
    expect(cmp.title()).toBe('Senior Backend Engineer');
    expect(cmp.company()).toBe('Acme Corp');
    expect(cmp.description()).toBe('Build great APIs.');
    expect(cmp.prefilledFromJob()).toBe(true);

    fixture.detectChanges();
    const header = fixture.nativeElement.querySelector('.job-context');
    expect(header).not.toBeNull();
    expect(header.textContent).toContain('Senior Backend Engineer');
    expect(header.textContent).toContain('Acme Corp');
  });

  it('degrades to the manual form with a notice when the job fetch fails', () => {
    const fixture = mount({
      jobId: 'job-1',
      getJob: () => throwError(() => new Error('boom')),
    });
    const cmp = fixture.componentInstance;

    expect(cmp.prefilledFromJob()).toBe(false);
    expect(cmp.prefillNotice()).not.toBe('');
    expect(cmp.title()).toBe('');

    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.job-context')).toBeNull();
    expect(fixture.nativeElement.querySelector('.alert-warning')).not.toBeNull();
  });

  it('creates an application from manual entry and navigates to the CV tab', () => {
    const navigate = vi.fn();
    const createManual = vi.fn(() => of({ id: 'app-1' }));
    const route = {
      snapshot: { queryParamMap: { get: () => null } },
    };
    TestBed.configureTestingModule({
      imports: [OptimizationComponent],
      providers: [
        { provide: ActivatedRoute, useValue: route },
        { provide: IngestionService, useValue: { getJob: () => of(makeJob()) } },
        { provide: ApplicationsService, useValue: { createManual } },
        { provide: Router, useValue: { navigate } },
      ],
    });
    const fixture = TestBed.createComponent(OptimizationComponent);
    fixture.detectChanges();
    const cmp = fixture.componentInstance;

    cmp.title.set('Eng');
    cmp.company.set('Acme');
    cmp.description.set('Do stuff');
    cmp.submit();

    expect(createManual).toHaveBeenCalledWith({
      title: 'Eng',
      company: 'Acme',
      description: 'Do stuff',
    });
    expect(navigate).toHaveBeenCalledWith(['/dashboard/applications', 'app-1'], {
      queryParams: { tab: 'cv' },
    });
  });
});
