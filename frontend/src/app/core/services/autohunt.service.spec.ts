import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { AutohuntService } from './autohunt.service';
import { environment } from '../../../environments/environment';
import { Digest } from '../../pages/autohunt/models/digest.model';

function makeDigest(over: Partial<Digest> = {}): Digest {
  return {
    id: 'dig-1',
    created_at: '2026-06-07T00:00:00Z',
    cutoff_at: '2026-06-06T00:00:00Z',
    job_count: 1,
    entries: [
      { job_id: 'job-1', title: 'Backend Engineer', company: 'Acme', url: null, score: 0.87 },
    ],
    ...over,
  };
}

describe('AutohuntService', () => {
  let service: AutohuntService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [AutohuntService, provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(AutohuntService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('latest GETs /autohunt/digests/latest and returns the digest on 200', () => {
    const digest = makeDigest();
    let result: Digest | null | undefined;
    service.latest().subscribe((d) => (result = d));

    const req = httpMock.expectOne(`${environment.apiUrl}/autohunt/digests/latest`);
    expect(req.request.method).toBe('GET');
    req.flush(digest);

    expect(result).toEqual(digest);
  });

  it('latest maps a 204 No Content to null', () => {
    let result: Digest | null | undefined;
    service.latest().subscribe((d) => (result = d));

    const req = httpMock.expectOne(`${environment.apiUrl}/autohunt/digests/latest`);
    expect(req.request.method).toBe('GET');
    req.flush(null, { status: 204, statusText: 'No Content' });

    expect(result).toBeNull();
  });

  it('listRecent GETs /autohunt/digests with the limit param', () => {
    service.listRecent().subscribe();
    const req = httpMock.expectOne((r) => r.url === `${environment.apiUrl}/autohunt/digests`);
    expect(req.request.method).toBe('GET');
    expect(req.request.params.get('limit')).toBe('20');
    req.flush([]);
  });

  it('listRecent honors a custom limit', () => {
    service.listRecent(5).subscribe();
    const req = httpMock.expectOne((r) => r.url === `${environment.apiUrl}/autohunt/digests`);
    expect(req.request.params.get('limit')).toBe('5');
    req.flush([]);
  });

  it('run POSTs /autohunt/run with an empty body', () => {
    const digest = makeDigest();
    let result: Digest | undefined;
    service.run().subscribe((d) => (result = d));

    const req = httpMock.expectOne(`${environment.apiUrl}/autohunt/run`);
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({});
    req.flush(digest);

    expect(result).toEqual(digest);
  });
});
