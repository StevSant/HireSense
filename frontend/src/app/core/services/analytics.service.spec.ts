import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { AnalyticsService } from './analytics.service';
import { environment } from '../../../environments/environment';

describe('AnalyticsService', () => {
  let service: AnalyticsService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [AnalyticsService, provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(AnalyticsService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('funnel GETs /analytics/funnel', () => {
    service.funnel().subscribe();
    const req = httpMock.expectOne(`${environment.apiUrl}/analytics/funnel`);
    expect(req.request.method).toBe('GET');
    req.flush({ stages: [], rejected: 0, current_rejected: 0, total_applications: 0 });
  });

  it('market GETs /analytics/market', () => {
    service.market().subscribe();
    const req = httpMock.expectOne(`${environment.apiUrl}/analytics/market`);
    expect(req.request.method).toBe('GET');
    req.flush({
      top_skills: [],
      remote_mix: {},
      posting_trend: [],
      salary_distribution: {
        currency: null,
        min_annual: null,
        median_annual: null,
        max_annual: null,
        parsed_count: 0,
        unparsed_count: 0,
        other_currency_count: 0,
        disclosed_pct: 0,
      },
    });
  });

  it('skillGap GETs /analytics/skill-gap', () => {
    service.skillGap().subscribe();
    const req = httpMock.expectOne(`${environment.apiUrl}/analytics/skill-gap`);
    expect(req.request.method).toBe('GET');
    req.flush({ has_profile: false, missing: [] });
  });

  it('targetSalary GETs /analytics/target-salary', () => {
    service.targetSalary().subscribe();
    const req = httpMock.expectOne(`${environment.apiUrl}/analytics/target-salary`);
    expect(req.request.method).toBe('GET');
    req.flush({
      insufficient_data: true,
      currency: null,
      p25_annual: null,
      median_annual: null,
      p75_annual: null,
      sample_size: 0,
    });
  });
});
