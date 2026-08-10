import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { ApplicationsService } from './applications.service';
import { environment } from '../../../environments/environment';
import { ApplicationListItem } from '@core/contracts/application-list-item.model';
import { PagedResult } from '@core/contracts/paged-result.model';

const BASE = `${environment.apiUrl}/applications`;

function row(id: number, status = 'saved'): ApplicationListItem {
  return {
    id: `app-${id}`,
    title: `Role ${id}`,
    company: `Company ${id}`,
    status,
    url: null,
    created_at: '2026-01-01T00:00:00Z',
    has_match: false,
    has_optimization: false,
    has_prep: false,
    latest_match_score: null,
    job_id: null,
    notes: null,
    applied_at: null,
    location: null,
    remote_modality: null,
    salary_range: null,
    source: null,
    posted_date: null,
  } as unknown as ApplicationListItem;
}

describe('ApplicationsService', () => {
  let service: ApplicationsService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [ApplicationsService, provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(ApplicationsService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  describe('listPage', () => {
    it('sends the requested limit and offset', () => {
      service.listPage(50, 100).subscribe();

      const req = httpMock.expectOne((r) => r.url === BASE);
      expect(req.request.method).toBe('GET');
      expect(req.request.params.get('limit')).toBe('50');
      expect(req.request.params.get('offset')).toBe('100');
      req.flush([], { headers: { 'X-Total-Count': '0' } });
    });

    it('reads the total out of the X-Total-Count header', () => {
      let result: PagedResult<ApplicationListItem> | null = null;
      service.listPage(20, 0).subscribe((r) => (result = r));

      httpMock
        .expectOne((r) => r.url === BASE)
        .flush([row(1)], { headers: { 'X-Total-Count': '243' } });

      expect(result!.total).toBe(243);
      expect(result!.items).toHaveLength(1);
    });
  });

  describe('listAll', () => {
    // Regression: the old list() took no arguments, so it always fetched the
    // backend's default first page (100) and discarded X-Total-Count. Every
    // application past row 100 was silently dropped — and the applications
    // page computes its status-tab badge counts from that truncated set, so
    // the numbers rendered on screen were wrong.
    it('keeps requesting pages until the server total is covered', () => {
      let result: PagedResult<ApplicationListItem> | null = null;
      service.listAll().subscribe((r) => (result = r));

      const first = httpMock.expectOne((r) => r.url === BASE && r.params.get('offset') === '0');
      const pageSize = Number(first.request.params.get('limit'));
      expect(pageSize).toBeGreaterThan(0);
      first.flush(
        Array.from({ length: pageSize }, (_, i) => row(i)),
        { headers: { 'X-Total-Count': String(pageSize + 30) } },
      );

      const second = httpMock.expectOne(
        (r) => r.url === BASE && r.params.get('offset') === String(pageSize),
      );
      second.flush(
        Array.from({ length: 30 }, (_, i) => row(pageSize + i)),
        { headers: { 'X-Total-Count': String(pageSize + 30) } },
      );

      expect(result!.items).toHaveLength(pageSize + 30);
      expect(result!.total).toBe(pageSize + 30);
      // The rows beyond the first page are the ones the old code lost.
      expect(result!.items.at(-1)!.id).toBe(`app-${pageSize + 29}`);
    });

    it('issues a single request when everything fits on one page', () => {
      let result: PagedResult<ApplicationListItem> | null = null;
      service.listAll().subscribe((r) => (result = r));

      httpMock
        .expectOne((r) => r.url === BASE)
        .flush([row(1), row(2)], { headers: { 'X-Total-Count': '2' } });

      expect(result!.items).toHaveLength(2);
      httpMock.verify();
    });
  });

  describe('listAllCoverLetters', () => {
    it('walks the cover letter library past the first page', () => {
      const url = `${BASE}/cover-letters`;
      let result: PagedResult<unknown> | null = null;
      service.listAllCoverLetters().subscribe((r) => (result = r));

      const first = httpMock.expectOne((r) => r.url === url && r.params.get('offset') === '0');
      const pageSize = Number(first.request.params.get('limit'));
      first.flush(
        Array.from({ length: pageSize }, (_, i) => ({ id: `cl-${i}` })),
        { headers: { 'X-Total-Count': String(pageSize + 5) } },
      );

      httpMock
        .expectOne((r) => r.url === url && r.params.get('offset') === String(pageSize))
        .flush(
          Array.from({ length: 5 }, (_, i) => ({ id: `cl-${pageSize + i}` })),
          { headers: { 'X-Total-Count': String(pageSize + 5) } },
        );

      expect(result!.items).toHaveLength(pageSize + 5);
    });
  });
});
