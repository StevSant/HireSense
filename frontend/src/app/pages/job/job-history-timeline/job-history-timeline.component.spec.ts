import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { JobHistoryTimelineComponent } from './job-history-timeline.component';

describe('JobHistoryTimelineComponent', () => {
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [JobHistoryTimelineComponent],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    // Guards against a test that fires an unexpected request, or leaves one
    // outstanding — the DOM-assertion rewrite dropped the per-test verify()
    // calls this replaces.
    httpMock.verify();
  });

  function createComponent(jobId = 'job-1') {
    const fixture = TestBed.createComponent(JobHistoryTimelineComponent);
    fixture.componentRef.setInput('jobId', jobId);
    fixture.detectChanges();
    return fixture;
  }

  function flush(fixture: ReturnType<typeof createComponent>, events: unknown[]) {
    const req = httpMock.expectOne('/api/ingestion/jobs/job-1/history');
    req.flush({ events });
    fixture.detectChanges();
  }

  function itemLabels(fixture: ReturnType<typeof createComponent>): string[] {
    return Array.from(
      (fixture.nativeElement as HTMLElement).querySelectorAll('.job-history-label'),
    ).map((el) => el.textContent?.trim() ?? '');
  }

  it('renders one entry per event, newest first', () => {
    const fixture = createComponent();
    flush(fixture, [
      {
        job_id: 'job-1',
        event: 'updated',
        changed_fields: {},
        reason: null,
        occurred_at: '2026-08-19T10:00:00Z',
      },
      {
        job_id: 'job-1',
        event: 'inserted',
        changed_fields: {},
        reason: null,
        occurred_at: '2026-08-18T10:00:00Z',
      },
    ]);
    const items = (fixture.nativeElement as HTMLElement).querySelectorAll('.job-history-item');
    expect(items.length).toBe(2);
    expect(itemLabels(fixture)).toEqual(['Updated', 'Ingested']);
  });

  it('renders two identical same-timestamp events without a duplicate-key error', () => {
    const duplicate = {
      job_id: 'job-1',
      event: 'updated',
      changed_fields: {},
      reason: null,
      occurred_at: '2026-08-19T10:00:00Z',
    };
    const fixture = createComponent();
    flush(fixture, [duplicate, { ...duplicate }]);
    const items = (fixture.nativeElement as HTMLElement).querySelectorAll('.job-history-item');
    expect(items.length).toBe(2);
  });

  it('renders an inserted event as "Ingested"', () => {
    const fixture = createComponent();
    flush(fixture, [
      {
        job_id: 'job-1',
        event: 'inserted',
        changed_fields: {},
        reason: null,
        occurred_at: '2026-08-18T10:00:00Z',
      },
    ]);
    expect(itemLabels(fixture)).toEqual(['Ingested']);
  });

  it('shows which fetch produced an event when run provenance is available', () => {
    const fixture = createComponent();
    flush(fixture, [
      {
        job_id: 'job-1',
        event: 'inserted',
        changed_fields: {},
        reason: null,
        occurred_at: '2026-08-18T10:00:00Z',
        run_id: '12345678-abcd',
        run_trigger: 'fetch',
      },
    ]);
    const run = (fixture.nativeElement as HTMLElement).querySelector('.job-history-run');
    expect(run?.textContent).toContain('Manual fetch');
    expect(run?.textContent).toContain('12345678');
  });

  it('renders a reopened event as "Reopened"', () => {
    const fixture = createComponent();
    flush(fixture, [
      {
        job_id: 'job-1',
        event: 'reopened',
        changed_fields: {},
        reason: null,
        occurred_at: '2026-08-18T10:00:00Z',
      },
    ]);
    expect(itemLabels(fixture)).toEqual(['Reopened']);
  });

  it('renders a closed event with its reason in human words', () => {
    const fixture = createComponent();
    flush(fixture, [
      {
        job_id: 'job-1',
        event: 'closed',
        changed_fields: {},
        reason: 'probe_404',
        occurred_at: '2026-08-18T10:00:00Z',
      },
    ]);
    expect(itemLabels(fixture)).toEqual(['Closed']);
    const reason = (fixture.nativeElement as HTMLElement).querySelector('.job-history-reason');
    expect(reason?.textContent?.trim()).toBe('listing returned 404');
  });

  it('renders a tracked field change as "was X, now Y"', () => {
    const fixture = createComponent();
    flush(fixture, [
      {
        job_id: 'job-1',
        event: 'updated',
        changed_fields: { salary_range: { old: null, new: '$180-200K' } },
        reason: null,
        occurred_at: '2026-08-18T10:00:00Z',
      },
    ]);
    const changeItems = Array.from(
      (fixture.nativeElement as HTMLElement).querySelectorAll('.job-history-changes li'),
    ).map((el) => el.textContent?.trim());
    expect(changeItems).toEqual(['Salary: was blank, now $180-200K']);
  });

  it('renders a description change as "Description updated" with no values', () => {
    const fixture = createComponent();
    flush(fixture, [
      {
        job_id: 'job-1',
        event: 'updated',
        changed_fields: { description: { changed: true } },
        reason: null,
        occurred_at: '2026-08-18T10:00:00Z',
      },
    ]);
    const changeItems = Array.from(
      (fixture.nativeElement as HTMLElement).querySelectorAll('.job-history-changes li'),
    ).map((el) => el.textContent?.trim());
    expect(changeItems).toEqual(['Description updated']);
  });

  it('renders the predates-the-audit-trail empty state when there are no events', () => {
    const fixture = createComponent();
    flush(fixture, []);
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('No recorded history');
    expect(text).toContain('19 Aug 2026');
  });

  it('renders an error state when the request fails', () => {
    const fixture = createComponent();
    const req = httpMock.expectOne('/api/ingestion/jobs/job-1/history');
    req.flush('boom', { status: 500, statusText: 'Server Error' });
    fixture.detectChanges();
    expect(fixture.componentInstance.error()).toBeTruthy();
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text.toLowerCase()).toContain('failed');
  });

  it('falls back to a safe label for an event type the frontend does not recognize', () => {
    const fixture = createComponent();
    flush(fixture, [
      {
        job_id: 'job-1',
        event: 'archived',
        changed_fields: {},
        reason: null,
        occurred_at: '2026-08-18T10:00:00Z',
      },
    ]);
    const labels = itemLabels(fixture);
    expect(labels).toEqual(['Event']);
    expect(labels[0]).not.toBe('archived');
  });

  it('falls back to neutral wording for a reason code the frontend does not recognize', () => {
    const fixture = createComponent();
    flush(fixture, [
      {
        job_id: 'job-1',
        event: 'closed',
        changed_fields: {},
        reason: 'manual_admin_close',
        occurred_at: '2026-08-18T10:00:00Z',
      },
    ]);
    const reason = (fixture.nativeElement as HTMLElement).querySelector('.job-history-reason');
    expect(reason?.textContent?.trim()).toBe('reason not recorded');
    expect(reason?.textContent).not.toContain('manual_admin_close');
  });

  it('falls back to a neutral field label for a field the frontend does not recognize', () => {
    const fixture = createComponent();
    flush(fixture, [
      {
        job_id: 'job-1',
        event: 'updated',
        changed_fields: { seniority_level: { old: 'Junior', new: 'Senior' } },
        reason: null,
        occurred_at: '2026-08-18T10:00:00Z',
      },
    ]);
    const changeItems = Array.from(
      (fixture.nativeElement as HTMLElement).querySelectorAll('.job-history-changes li'),
    ).map((el) => el.textContent?.trim());
    expect(changeItems).toEqual(['Field: was Junior, now Senior']);
  });
});
