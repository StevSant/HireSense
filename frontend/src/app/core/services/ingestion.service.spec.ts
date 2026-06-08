import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { IngestionService } from './ingestion.service';
import { environment } from '../../../environments/environment';

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
    const req = httpMock.expectOne((r) => r.url === `${environment.apiUrl}/ingestion/jobs`);
    expect(req.request.method).toBe('GET');
    expect(req.request.params.has('rescore')).toBe(false);
    req.flush(empty);
  });

  it('queryJobs sends rescore=false for the sort-only fast path (#76)', () => {
    service.queryJobs('boards', 2, 20, {}, false, false).subscribe();
    const req = httpMock.expectOne((r) => r.url === `${environment.apiUrl}/ingestion/jobs`);
    expect(req.request.params.get('rescore')).toBe('false');
    req.flush(empty);
  });

  it('queryJobs omits rescore when rescore=true is passed explicitly', () => {
    service.queryJobs('boards', 1, 20, {}, false, true).subscribe();
    const req = httpMock.expectOne((r) => r.url === `${environment.apiUrl}/ingestion/jobs`);
    expect(req.request.params.has('rescore')).toBe(false);
    req.flush(empty);
  });
});
