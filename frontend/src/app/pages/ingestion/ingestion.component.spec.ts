import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { IngestionComponent } from './ingestion.component';
import { environment } from '../../../environments/environment';

const jobsPayload = (connectionsByJob: Record<string, number> = {}) => ({
  jobs: [
    {
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
    },
  ],
  total: 1,
  page: 1,
  page_size: 20,
  total_pages: 1,
  connections_by_job: connectionsByJob,
});

describe('IngestionComponent — connections badge', () => {
  let httpMock: HttpTestingController;

  beforeEach(async () => {
    localStorage.clear();
    await TestBed.configureTestingModule({
      imports: [IngestionComponent],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('renders the connections badge for a job present in connections_by_job', () => {
    const fixture = TestBed.createComponent(IngestionComponent);
    fixture.detectChanges();

    // Flush portals call (order may vary)
    httpMock
      .match((r) => r.url === `${environment.apiUrl}/ingestion/portals`)
      .forEach((r) => r.flush([]));

    // <app-job-filters>'s guaranteed single initial emission is the only
    // source of the first load (see the loadJobs$ comment in
    // ingestion.component.ts) — exactly one request, nothing to cancel.
    const jobReqs = httpMock.match((r) => r.url === `${environment.apiUrl}/ingestion/jobs`);
    expect(jobReqs.length).toBe(1);
    jobReqs[0].flush(jobsPayload({ 'job-1': 3 }));

    fixture.detectChanges();

    const badge = (fixture.nativeElement as HTMLElement).querySelector('.connections-badge');
    expect(badge).toBeTruthy();
    expect(badge!.textContent?.trim()).toContain('3');
    expect(badge!.getAttribute('title')).toContain('3 LinkedIn connections');
  });

  it('cancels the in-flight job request when a newer one starts (last wins)', () => {
    const fixture = TestBed.createComponent(IngestionComponent);
    const component = fixture.componentInstance;
    fixture.detectChanges();

    httpMock
      .match((r) => r.url === `${environment.apiUrl}/ingestion/portals`)
      .forEach((r) => r.flush([]));
    // Drain the single initial load issued by <app-job-filters>'s emission.
    httpMock.match((r) => r.url === `${environment.apiUrl}/ingestion/jobs`)[0].flush(jobsPayload());

    // Two rapid loads: the first must be cancelled by switchMap, the second wins.
    component.loadJobs();
    component.loadJobs();
    const reqs = httpMock.match((r) => r.url === `${environment.apiUrl}/ingestion/jobs`);
    expect(reqs.length).toBe(2);
    expect(reqs[0].cancelled).toBe(true);
    expect(reqs[1].cancelled).toBe(false);

    reqs[1].flush(jobsPayload({ 'job-1': 5 }));
    fixture.detectChanges();
    expect(component.jobs().length).toBe(1);
    expect(component.loading()).toBe(false);
  });
});

describe('IngestionComponent — exactly one initial job request', () => {
  let httpMock: HttpTestingController;

  beforeEach(async () => {
    localStorage.clear();
    await TestBed.configureTestingModule({
      imports: [IngestionComponent],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    localStorage.clear();
    httpMock.verify();
  });

  function flushPortals(mock: HttpTestingController): void {
    mock.match((r) => r.url === `${environment.apiUrl}/ingestion/portals`).forEach((r) => r.flush([]));
  }

  it('fires exactly one request when no location is stored', () => {
    const fixture = TestBed.createComponent(IngestionComponent);
    fixture.detectChanges();
    flushPortals(httpMock);

    const jobReqs = httpMock.match((r) => r.url === `${environment.apiUrl}/ingestion/jobs`);
    expect(jobReqs.length).toBe(1);
    expect(jobReqs[0].cancelled).toBeFalsy();
    jobReqs[0].flush(jobsPayload());
  });

  it('fires exactly one request, carrying the restored filter, when a location is stored', () => {
    localStorage.setItem('hiresense.user_location', 'Chile');
    localStorage.setItem('hiresense.strict_location_match', 'true');

    const fixture = TestBed.createComponent(IngestionComponent);
    fixture.detectChanges();
    flushPortals(httpMock);

    const jobReqs = httpMock.match((r) => r.url === `${environment.apiUrl}/ingestion/jobs`);
    expect(jobReqs.length).toBe(1);
    expect(jobReqs[0].cancelled).toBeFalsy();
    expect(jobReqs[0].request.params.get('user_location')).toBe('Chile');
    expect(jobReqs[0].request.params.get('strict_location')).toBe('true');
    jobReqs[0].flush(jobsPayload());
  });
});

describe('IngestionComponent — visibility-gated revalidation poll', () => {
  let httpMock: HttpTestingController;
  let originalVisibility: PropertyDescriptor | undefined;

  beforeEach(async () => {
    localStorage.clear();
    vi.useFakeTimers();
    originalVisibility = Object.getOwnPropertyDescriptor(document, 'visibilityState');
    await TestBed.configureTestingModule({
      imports: [IngestionComponent],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
    vi.useRealTimers();
    if (originalVisibility) {
      Object.defineProperty(document, 'visibilityState', originalVisibility);
    }
  });

  function setVisibility(state: 'visible' | 'hidden'): void {
    Object.defineProperty(document, 'visibilityState', { value: state, configurable: true });
  }

  function jobsReqs(mock: HttpTestingController) {
    return mock.match((r) => r.url === `${environment.apiUrl}/ingestion/jobs`);
  }

  it('skips poll ticks while the tab is hidden and resumes once visible', () => {
    const fixture = TestBed.createComponent(IngestionComponent);
    const component = fixture.componentInstance;
    fixture.detectChanges();

    httpMock
      .match((r) => r.url === `${environment.apiUrl}/ingestion/portals`)
      .forEach((r) => r.flush([]));
    jobsReqs(httpMock)[0].flush(jobsPayload());

    component.revalidate();
    httpMock
      .expectOne(`${environment.apiUrl}/ingestion/revalidate`)
      .flush({ started: true, closed: 0, closed_ids: [] });
    // revalidate()'s own immediate reload of the visible page.
    jobsReqs(httpMock)[0].flush(jobsPayload());

    setVisibility('hidden');
    vi.advanceTimersByTime(15000);
    expect(jobsReqs(httpMock).length).toBe(0);

    setVisibility('visible');
    vi.advanceTimersByTime(15000);
    const polled = jobsReqs(httpMock);
    expect(polled.length).toBe(1);
    polled[0].flush(jobsPayload());
  });
});
