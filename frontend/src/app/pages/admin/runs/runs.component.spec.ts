import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { RunsComponent } from './runs.component';

describe('RunsComponent', () => {
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [RunsComponent],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  function flushRuns(fixture: ReturnType<typeof TestBed.createComponent>, runs: unknown[]) {
    const req = httpMock.expectOne((r) => r.url === '/api/ingestion/runs');
    req.flush({ runs });
    fixture.detectChanges();
  }

  it('renders one row per run with its totals', () => {
    const fixture = TestBed.createComponent(RunsComponent);
    fixture.detectChanges();
    flushRuns(fixture, [
      {
        id: 'run-1',
        started_at: '2026-08-19T10:00:00Z',
        finished_at: '2026-08-19T10:05:00Z',
        trigger: 'fetch',
        status: 'completed',
        inserted: 3,
        updated: 2,
        reopened: 1,
        closed: 0,
      },
    ]);

    const rows = fixture.nativeElement.querySelectorAll('tbody tr.run-row');
    expect(rows.length).toBe(1);
    const text = rows[0].textContent;
    expect(text).toContain('3');
    expect(text).toContain('2');
    expect(text).toContain('1');
    expect(text).toContain('0');
  });

  it('shows a running run with no duration', () => {
    const fixture = TestBed.createComponent(RunsComponent);
    fixture.detectChanges();
    flushRuns(fixture, [
      {
        id: 'run-2',
        started_at: '2026-08-19T10:00:00Z',
        finished_at: null,
        trigger: 'scheduler',
        status: 'running',
        inserted: 0,
        updated: 0,
        reopened: 0,
        closed: 0,
      },
    ]);

    const durationCell = fixture.nativeElement.querySelector('tbody tr.run-row td.duration');
    expect(durationCell.textContent).not.toContain('NaN');
    expect(durationCell.textContent.trim()).toBe('—');
  });

  it('formats a finished run duration from started_at and finished_at', () => {
    const fixture = TestBed.createComponent(RunsComponent);
    fixture.detectChanges();
    flushRuns(fixture, [
      {
        id: 'run-3',
        started_at: '2026-08-19T10:00:00Z',
        finished_at: '2026-08-19T10:05:30Z',
        trigger: 'fetch',
        status: 'completed',
        inserted: 0,
        updated: 0,
        reopened: 0,
        closed: 0,
      },
    ]);

    const durationCell = fixture.nativeElement.querySelector('tbody tr.run-row td.duration');
    expect(durationCell.textContent).toContain('5m');
    expect(durationCell.textContent).toContain('30s');
  });

  it('labels the trigger as Manual fetch or Scheduled', () => {
    const fixture = TestBed.createComponent(RunsComponent);
    fixture.detectChanges();
    flushRuns(fixture, [
      {
        id: 'run-4',
        started_at: '2026-08-19T10:00:00Z',
        finished_at: '2026-08-19T10:01:00Z',
        trigger: 'fetch',
        status: 'completed',
        inserted: 0,
        updated: 0,
        reopened: 0,
        closed: 0,
      },
      {
        id: 'run-5',
        started_at: '2026-08-19T10:00:00Z',
        finished_at: '2026-08-19T10:01:00Z',
        trigger: 'scheduler',
        status: 'completed',
        inserted: 0,
        updated: 0,
        reopened: 0,
        closed: 0,
      },
    ]);

    const rows = fixture.nativeElement.querySelectorAll('tbody tr.run-row');
    expect(rows[0].textContent).toContain('Manual fetch');
    expect(rows[1].textContent).toContain('Scheduled');
  });

  it('expands a row to load and show that run events', () => {
    const fixture = TestBed.createComponent(RunsComponent);
    fixture.detectChanges();
    flushRuns(fixture, [
      {
        id: 'run-6',
        started_at: '2026-08-19T10:00:00Z',
        finished_at: '2026-08-19T10:01:00Z',
        trigger: 'fetch',
        status: 'completed',
        inserted: 1,
        updated: 0,
        reopened: 0,
        closed: 0,
      },
    ]);

    const toggle = fixture.nativeElement.querySelector('tbody tr.run-row button.expand-toggle');
    toggle.click();
    fixture.detectChanges();

    const detailReq = httpMock.expectOne((r) => r.url === '/api/ingestion/runs/run-6');
    detailReq.flush({
      run: {
        id: 'run-6',
        started_at: '2026-08-19T10:00:00Z',
        finished_at: '2026-08-19T10:01:00Z',
        trigger: 'fetch',
        status: 'completed',
        inserted: 1,
        updated: 0,
        reopened: 0,
        closed: 0,
      },
      events: [
        {
          job_id: 'job-1',
          job_title: 'Senior Backend Engineer',
          job_company: 'Acme',
          job_source: 'greenhouse',
          event: 'inserted',
          changed_fields: {},
          reason: null,
          occurred_at: '2026-08-19T10:00:30Z',
        },
      ],
    });
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Senior Backend Engineer');
    expect(fixture.nativeElement.textContent).toContain('Acme');
    expect(
      (fixture.nativeElement as HTMLElement).querySelector(
        'a.event-job[href="/dashboard/job/job-1"]',
      ),
    ).not.toBeNull();

    // Collapsing and re-expanding must not re-fetch.
    toggle.click();
    fixture.detectChanges();
    toggle.click();
    fixture.detectChanges();
    httpMock.expectNone((r) => r.url === '/api/ingestion/runs/run-6');
  });

  it('renders an empty state when there are no runs yet', () => {
    const fixture = TestBed.createComponent(RunsComponent);
    fixture.detectChanges();
    flushRuns(fixture, []);

    expect(fixture.nativeElement.textContent).toContain('No ingestion runs');
  });

  it('renders an error state when the request fails', () => {
    const fixture = TestBed.createComponent(RunsComponent);
    fixture.detectChanges();
    const req = httpMock.expectOne((r) => r.url === '/api/ingestion/runs');
    req.flush({ message: 'boom' }, { status: 500, statusText: 'Server Error' });
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Failed to load');
  });

  it('does not leak one run failed-event-fetch error onto another run already loaded from cache', () => {
    const fixture = TestBed.createComponent(RunsComponent);
    fixture.detectChanges();
    flushRuns(fixture, [
      {
        id: 'run-a',
        started_at: '2026-08-19T10:00:00Z',
        finished_at: '2026-08-19T10:01:00Z',
        trigger: 'fetch',
        status: 'completed',
        inserted: 0,
        updated: 0,
        reopened: 0,
        closed: 0,
      },
      {
        id: 'run-c',
        started_at: '2026-08-19T11:00:00Z',
        finished_at: '2026-08-19T11:01:00Z',
        trigger: 'fetch',
        status: 'completed',
        inserted: 0,
        updated: 0,
        reopened: 0,
        closed: 0,
      },
    ]);

    const rows = fixture.nativeElement.querySelectorAll('tbody tr.run-row');
    const toggleA = rows[0].querySelector('button.expand-toggle');
    const toggleC = rows[1].querySelector('button.expand-toggle');

    // Expand run A, whose detail fetch fails.
    toggleA.click();
    fixture.detectChanges();
    httpMock
      .expectOne((r) => r.url === '/api/ingestion/runs/run-a')
      .flush({ message: 'boom' }, { status: 500, statusText: 'Server Error' });
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Failed to load run events');

    // Collapse A.
    toggleA.click();
    fixture.detectChanges();

    // Expand run C for the first time — it fetches successfully.
    toggleC.click();
    fixture.detectChanges();
    httpMock
      .expectOne((r) => r.url === '/api/ingestion/runs/run-c')
      .flush({
        run: {
          id: 'run-c',
          started_at: '2026-08-19T11:00:00Z',
          finished_at: '2026-08-19T11:01:00Z',
          trigger: 'fetch',
          status: 'completed',
          inserted: 0,
          updated: 0,
          reopened: 0,
          closed: 0,
        },
        events: [
          {
            job_id: 'job-c',
            event: 'inserted',
            changed_fields: {},
            reason: null,
            occurred_at: '2026-08-19T11:00:30Z',
          },
        ],
      });
    fixture.detectChanges();

    // Collapse C, then re-expand it — this is a cache hit, no new request.
    toggleC.click();
    fixture.detectChanges();
    toggleC.click();
    fixture.detectChanges();

    const expandedRow = fixture.nativeElement.querySelector('tr.run-events-row');
    expect(expandedRow.textContent).toContain('job-c');
    expect(expandedRow.textContent).not.toContain('Failed to load');
  });
});
