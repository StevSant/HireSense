import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { OpportunitiesService } from './opportunities.service';
import { environment } from '../../../environments/environment';

describe('OpportunitiesService', () => {
  let service: OpportunitiesService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [OpportunitiesService, provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(OpportunitiesService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('list GETs /opportunities with filters', () => {
    service.list({ page: 2, pageSize: 25, kind: 'conference', fundedOnly: true }).subscribe();
    const req = httpMock.expectOne(
      (r) =>
        r.url === `${environment.apiUrl}/opportunities` &&
        r.params.get('page') === '2' &&
        r.params.get('page_size') === '25' &&
        r.params.get('kind') === 'conference' &&
        r.params.get('funded_only') === 'true',
    );
    expect(req.request.method).toBe('GET');
    req.flush({ items: [], total: 0, page: 2, page_size: 25 });
  });

  it('fetch POSTs /opportunities/fetch', () => {
    service.fetch().subscribe();
    const req = httpMock.expectOne(`${environment.apiUrl}/opportunities/fetch`);
    expect(req.request.method).toBe('POST');
    req.flush({ sources: {}, inserted: 0, updated: 0, reopened: 0, unchanged: 0, errors: [] });
  });
});
