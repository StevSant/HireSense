import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { PreferenceService } from './preference.service';
import { environment } from '../../../environments/environment';

describe('PreferenceService', () => {
  let service: PreferenceService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [PreferenceService, provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(PreferenceService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('submitFeedback POSTs job_id and kind', () => {
    service.submitFeedback('job-1', 'thumbs_up').subscribe();
    const req = httpMock.expectOne(`${environment.apiUrl}/preference/feedback`);
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ job_id: 'job-1', kind: 'thumbs_up' });
    req.flush({ id: 's1', job_id: 'job-1', kind: 'thumbs_up', created_at: null });
  });

  it('explain GETs /preference/explain', () => {
    service.explain().subscribe();
    const req = httpMock.expectOne(`${environment.apiUrl}/preference/explain`);
    expect(req.request.method).toBe('GET');
    req.flush({
      active: false,
      total_signals: 0,
      positive_count: 0,
      negative_count: 0,
      counts_by_kind: {},
      drift_magnitude: 0,
    });
  });

  it('signals GETs /preference/signals', () => {
    service.signals().subscribe();
    const req = httpMock.expectOne(`${environment.apiUrl}/preference/signals`);
    expect(req.request.method).toBe('GET');
    req.flush([]);
  });

  it('reset POSTs to /preference/reset', () => {
    service.reset().subscribe();
    const req = httpMock.expectOne(`${environment.apiUrl}/preference/reset`);
    expect(req.request.method).toBe('POST');
    req.flush(null);
  });
});
