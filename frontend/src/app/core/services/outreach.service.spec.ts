import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { OutreachService } from './outreach.service';
import { environment } from '../../../environments/environment';

describe('OutreachService', () => {
  let service: OutreachService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [OutreachService, provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(OutreachService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('generate POSTs /outreach/generate with the request body', () => {
    const body = { application_id: 'app-1', contact_name: 'Jordan', channel: 'LinkedIn' };
    service.generate(body).subscribe();
    const req = httpMock.expectOne(`${environment.apiUrl}/outreach/generate`);
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual(body);
    req.flush({ message: 'Hello' });
  });

  it('record POSTs /outreach/record with the request body', () => {
    const body = { application_id: 'app-1', kind: 'sent' as const, message: 'Hi' };
    service.record(body).subscribe();
    const req = httpMock.expectOne(`${environment.apiUrl}/outreach/record`);
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual(body);
    req.flush({
      id: 'evt-1',
      application_id: 'app-1',
      kind: 'sent',
      contact_name: null,
      channel: null,
      message: 'Hi',
      created_at: null,
    });
  });

  it('listEvents GETs /outreach/events with the application_id param', () => {
    service.listEvents('app-1').subscribe();
    const req = httpMock.expectOne(`${environment.apiUrl}/outreach/events?application_id=app-1`);
    expect(req.request.method).toBe('GET');
    expect(req.request.params.get('application_id')).toBe('app-1');
    req.flush([]);
  });

  it('dueFollowups POSTs /outreach/nudge', () => {
    service.dueFollowups().subscribe();
    const req = httpMock.expectOne(`${environment.apiUrl}/outreach/nudge`);
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({});
    req.flush([]);
  });
});
