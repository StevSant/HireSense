import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { DraftsComponent } from './drafts.component';

describe('DraftsComponent', () => {
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [DraftsComponent],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    httpMock = TestBed.inject(HttpTestingController);
  });
  afterEach(() => httpMock.verify());

  it('loads drafts on init', () => {
    const fixture = TestBed.createComponent(DraftsComponent);
    fixture.detectChanges();
    const req = httpMock.expectOne('/api/autopilot/drafts?limit=20');
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
    expect(fixture.componentInstance.drafts().length).toBe(1);
  });

  it('starts preparation and refreshes the list', () => {
    const fixture = TestBed.createComponent(DraftsComponent);
    fixture.detectChanges();
    httpMock.expectOne('/api/autopilot/drafts?limit=20').flush([]);

    fixture.componentInstance.prepare();
    const run = httpMock.expectOne('/api/autopilot/run');
    expect(run.request.method).toBe('POST');
    run.flush({ status: 'started' });

    const refresh = httpMock.expectOne('/api/autopilot/drafts?limit=20');
    refresh.flush([
      {
        id: '2',
        job_id: 'j2',
        application_id: 'a2',
        job_title: 'Platform Engineer',
        company: 'Globex',
        status: 'pending',
        detail: null,
      },
    ]);

    expect(fixture.componentInstance.preparing()).toBe(false);
    expect(fixture.componentInstance.notice()).toContain('Preparation started');
    expect(fixture.componentInstance.drafts().length).toBe(1);
  });
});
