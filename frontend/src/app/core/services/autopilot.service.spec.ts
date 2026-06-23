import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { AutopilotService } from './autopilot.service';

describe('AutopilotService', () => {
  let service: AutopilotService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [AutopilotService, provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(AutopilotService);
    httpMock = TestBed.inject(HttpTestingController);
  });
  afterEach(() => httpMock.verify());

  it('lists drafts', () => {
    let result: unknown;
    service.listDrafts().subscribe((r) => (result = r));
    const req = httpMock.expectOne('/api/autopilot/drafts?limit=20');
    expect(req.request.method).toBe('GET');
    req.flush([
      {
        id: '1',
        job_id: 'j1',
        application_id: 'a1',
        job_title: 'Dev',
        company: 'Acme',
        status: 'drafted',
        detail: null,
      },
    ]);
    expect((result as unknown[]).length).toBe(1);
  });
});
