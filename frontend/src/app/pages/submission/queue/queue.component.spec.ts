import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { QueueComponent } from './queue.component';

const ESCALATED = {
  id: 'att-1',
  application_id: 'app-1',
  job_id: 'greenhouse:123',
  packet_id: 'pk-1',
  channel: 'greenhouse',
  target_url: 'https://boards.greenhouse.io/acme/jobs/1',
  status: 'escalated',
  attempt_no: 1,
  escalation_reason: 'Needs a human answer: Desired salary',
  escalated_fields: ['Desired salary'],
  evidence: {},
  created_at: null,
  finished_at: null,
};

describe('QueueComponent', () => {
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [QueueComponent],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    httpMock = TestBed.inject(HttpTestingController);
  });
  afterEach(() => httpMock.verify());

  function createAndLoad(rows: unknown[] = [ESCALATED]) {
    const fixture = TestBed.createComponent(QueueComponent);
    fixture.detectChanges();
    httpMock.expectOne('/api/submission/attempts?limit=50&status=escalated').flush(rows);
    fixture.detectChanges();
    return fixture;
  }

  it('loads only escalated attempts on init', () => {
    const fixture = createAndLoad();
    expect(fixture.componentInstance.attempts().length).toBe(1);
    expect(fixture.componentInstance.attempts()[0].job_id).toBe('greenhouse:123');
  });

  it('renders the escalation reason', () => {
    const fixture = createAndLoad();
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('Desired salary');
  });

  it('shows an empty state when nothing is waiting', () => {
    const fixture = createAndLoad([]);
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('Nothing waiting');
  });

  it('blocks resume until every escalated field is answered', () => {
    const fixture = createAndLoad();
    const component = fixture.componentInstance;
    expect(component.canResume(component.attempts()[0])).toBe(false);
    component.setAnswer('att-1', 'Desired salary', '70000 EUR');
    expect(component.canResume(component.attempts()[0])).toBe(true);
  });

  it('treats a whitespace-only answer as unanswered', () => {
    const fixture = createAndLoad();
    const component = fixture.componentInstance;
    component.setAnswer('att-1', 'Desired salary', '   ');
    expect(component.canResume(component.attempts()[0])).toBe(false);
  });

  it('posts the entered answers when resuming and reloads', () => {
    const fixture = createAndLoad();
    const component = fixture.componentInstance;
    component.setAnswer('att-1', 'Desired salary', '70000 EUR');
    component.resume(component.attempts()[0]);

    const req = httpMock.expectOne('/api/submission/attempts/att-1/resume');
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ answers: { 'Desired salary': '70000 EUR' } });
    req.flush({ ...ESCALATED, status: 'queued' });

    httpMock.expectOne('/api/submission/attempts?limit=50&status=escalated').flush([]);
    expect(component.notice()).toContain('will not be asked again');
  });

  it('abandons an attempt and reloads', () => {
    const fixture = createAndLoad();
    const component = fixture.componentInstance;
    component.abandon(component.attempts()[0]);

    const req = httpMock.expectOne('/api/submission/attempts/att-1/abandon');
    expect(req.request.method).toBe('POST');
    req.flush({ ...ESCALATED, status: 'abandoned' });

    httpMock.expectOne('/api/submission/attempts?limit=50&status=escalated').flush([]);
    expect(component.notice()).toContain('abandoned');
  });

  it('surfaces a load failure', () => {
    const fixture = TestBed.createComponent(QueueComponent);
    fixture.detectChanges();
    httpMock
      .expectOne('/api/submission/attempts?limit=50&status=escalated')
      .flush({ detail: 'boom' }, { status: 500, statusText: 'Server Error' });
    expect(fixture.componentInstance.error()).toBe('boom');
  });

  it('toggles a row open and closed', () => {
    const fixture = createAndLoad();
    const component = fixture.componentInstance;
    component.toggle('att-1');
    expect(component.expandedId()).toBe('att-1');
    component.toggle('att-1');
    expect(component.expandedId()).toBeNull();
  });
});
