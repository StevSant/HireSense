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

  function createComponent(jobId = 'job-1') {
    const fixture = TestBed.createComponent(JobHistoryTimelineComponent);
    fixture.componentRef.setInput('jobId', jobId);
    fixture.detectChanges();
    return fixture;
  }

  it('renders one entry per event, newest first', () => {
    const fixture = createComponent();
    const req = httpMock.expectOne('/api/ingestion/jobs/job-1/history');
    req.flush({
      events: [
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
      ],
    });
    fixture.detectChanges();
    expect(fixture.componentInstance.events().length).toBe(2);
    expect(fixture.componentInstance.events()[0].event).toBe('updated');
    httpMock.verify();
  });

  it('renders an inserted event as "Ingested"', () => {
    const fixture = createComponent();
    const req = httpMock.expectOne('/api/ingestion/jobs/job-1/history');
    req.flush({
      events: [
        {
          job_id: 'job-1',
          event: 'inserted',
          changed_fields: {},
          reason: null,
          occurred_at: '2026-08-18T10:00:00Z',
        },
      ],
    });
    fixture.detectChanges();
    const event = fixture.componentInstance.events()[0];
    expect(fixture.componentInstance.label(event)).toBe('Ingested');
    httpMock.verify();
  });

  it('renders a reopened event as "Reopened"', () => {
    const fixture = createComponent();
    const req = httpMock.expectOne('/api/ingestion/jobs/job-1/history');
    req.flush({
      events: [
        {
          job_id: 'job-1',
          event: 'reopened',
          changed_fields: {},
          reason: null,
          occurred_at: '2026-08-18T10:00:00Z',
        },
      ],
    });
    fixture.detectChanges();
    const event = fixture.componentInstance.events()[0];
    expect(fixture.componentInstance.label(event)).toBe('Reopened');
    httpMock.verify();
  });

  it('renders a closed event with its reason in human words', () => {
    const fixture = createComponent();
    const req = httpMock.expectOne('/api/ingestion/jobs/job-1/history');
    req.flush({
      events: [
        {
          job_id: 'job-1',
          event: 'closed',
          changed_fields: {},
          reason: 'probe_404',
          occurred_at: '2026-08-18T10:00:00Z',
        },
      ],
    });
    fixture.detectChanges();
    const event = fixture.componentInstance.events()[0];
    expect(fixture.componentInstance.label(event)).toBe('Closed');
    expect(fixture.componentInstance.reasonLabel(event.reason)).toBe('listing returned 404');
    httpMock.verify();
  });

  it('renders a tracked field change as "was X, now Y"', () => {
    const fixture = createComponent();
    const req = httpMock.expectOne('/api/ingestion/jobs/job-1/history');
    req.flush({
      events: [
        {
          job_id: 'job-1',
          event: 'updated',
          changed_fields: { salary_range: { old: null, new: '$180-200K' } },
          reason: null,
          occurred_at: '2026-08-18T10:00:00Z',
        },
      ],
    });
    fixture.detectChanges();
    const event = fixture.componentInstance.events()[0];
    expect(fixture.componentInstance.changes(event)).toEqual(['Salary: was blank, now $180-200K']);
    httpMock.verify();
  });

  it('renders a description change as "Description updated" with no values', () => {
    const fixture = createComponent();
    const req = httpMock.expectOne('/api/ingestion/jobs/job-1/history');
    req.flush({
      events: [
        {
          job_id: 'job-1',
          event: 'updated',
          changed_fields: { description: { changed: true } },
          reason: null,
          occurred_at: '2026-08-18T10:00:00Z',
        },
      ],
    });
    fixture.detectChanges();
    const event = fixture.componentInstance.events()[0];
    expect(fixture.componentInstance.changes(event)).toEqual(['Description updated']);
    httpMock.verify();
  });

  it('renders the predates-the-audit-trail empty state when there are no events', () => {
    const fixture = createComponent();
    const req = httpMock.expectOne('/api/ingestion/jobs/job-1/history');
    req.flush({ events: [] });
    fixture.detectChanges();
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('No recorded history');
    expect(text).toContain('19 Aug 2026');
    httpMock.verify();
  });

  it('renders an error state when the request fails', () => {
    const fixture = createComponent();
    const req = httpMock.expectOne('/api/ingestion/jobs/job-1/history');
    req.flush('boom', { status: 500, statusText: 'Server Error' });
    fixture.detectChanges();
    expect(fixture.componentInstance.error()).toBeTruthy();
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text.toLowerCase()).toContain('failed');
    httpMock.verify();
  });
});
