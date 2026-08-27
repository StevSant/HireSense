import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { IngestionService } from './ingestion.service';

describe('IngestionService', () => {
  let service: IngestionService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [IngestionService, provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(IngestionService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  const empty = { jobs: [], total: 0, page: 1, page_size: 20, total_pages: 0 };

  it('queryJobs omits the rescore param by default (full scoring pipeline)', () => {
    service.queryJobs('boards', 1, 20).subscribe();
    const req = httpMock.expectOne((r) => r.url === '/api/ingestion/jobs');
    expect(req.request.method).toBe('GET');
    expect(req.request.params.has('rescore')).toBe(false);
    req.flush(empty);
  });

  it('queryJobs sends rescore=false for the sort-only fast path (#76)', () => {
    service.queryJobs('boards', 2, 20, {}, false, false).subscribe();
    const req = httpMock.expectOne((r) => r.url === '/api/ingestion/jobs');
    expect(req.request.params.get('rescore')).toBe('false');
    req.flush(empty);
  });

  it('queryJobs omits rescore when rescore=true is passed explicitly', () => {
    service.queryJobs('boards', 1, 20, {}, false, true).subscribe();
    const req = httpMock.expectOne((r) => r.url === '/api/ingestion/jobs');
    expect(req.request.params.has('rescore')).toBe(false);
    req.flush(empty);
  });

  it('queryJobs sends the company filter param', () => {
    service.queryJobs('boards', 1, 100, { company: 'Acme' }).subscribe();
    const req = httpMock.expectOne((r) => r.url === '/api/ingestion/jobs');
    expect(req.request.params.get('company')).toBe('Acme');
    req.flush(empty);
  });

  it('queryJobs sends the opportunity pathway filters', () => {
    service
      .queryJobs('boards', 1, 20, {
        opportunity_type: 'internship',
        international_pathway: 'visa_sponsorship',
      })
      .subscribe();
    const req = httpMock.expectOne((r) => r.url === '/api/ingestion/jobs');
    expect(req.request.params.get('opportunity_type')).toBe('internship');
    expect(req.request.params.get('international_pathway')).toBe('visa_sponsorship');
    req.flush(empty);
  });

  it('requests job history for a job id', () => {
    service.getJobHistory('job-1').subscribe();
    const req = httpMock.expectOne((r) => r.url.endsWith('/ingestion/jobs/job-1/history'));
    expect(req.request.method).toBe('GET');
    req.flush({ events: [] });
  });

  it('passes the limit through as a query param', () => {
    service.getJobHistory('job-1', 10).subscribe();
    const req = httpMock.expectOne((r) => r.url.endsWith('/ingestion/jobs/job-1/history'));
    expect(req.request.params.get('limit')).toBe('10');
    req.flush({ events: [] });
  });

  it('requests the run list with limit and offset', () => {
    service.listRuns(5, 10).subscribe();
    const req = httpMock.expectOne((r) => r.url.endsWith('/ingestion/runs'));
    expect(req.request.params.get('limit')).toBe('5');
    expect(req.request.params.get('offset')).toBe('10');
    req.flush({ runs: [] });
  });

  it('requests one run by id', () => {
    service.getRun('run-1').subscribe();
    const req = httpMock.expectOne((r) => r.url.endsWith('/ingestion/runs/run-1'));
    expect(req.request.method).toBe('GET');
    req.flush({ run: {}, events: [] });
  });
});
