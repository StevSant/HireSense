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
});
