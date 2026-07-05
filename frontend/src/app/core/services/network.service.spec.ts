import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { NetworkService } from './network.service';
import { environment } from '../../../environments/environment';

describe('NetworkService', () => {
  let service: NetworkService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [NetworkService, provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(NetworkService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('import POSTs multipart to /network/import', () => {
    const file = new File(['col1,col2'], 'Connections.csv', { type: 'text/csv' });
    service.import(file).subscribe((res) => {
      expect(res.contacts).toBe(42);
      expect(res.imported_at).toBe('2026-06-09T00:00:00Z');
    });
    const req = httpMock.expectOne(`${environment.apiUrl}/network/import`);
    expect(req.request.method).toBe('POST');
    expect(req.request.body instanceof FormData).toBe(true);
    expect(req.request.body.get('file')).toBeTruthy();
    req.flush({ contacts: 42, imported_at: '2026-06-09T00:00:00Z' });
  });

  it('match GETs /network/match with company param', () => {
    service.match('Acme Corp').subscribe((res) => {
      expect(res.company_normalized).toBe('acme corp');
      expect(res.contacts.length).toBe(1);
    });
    const req = httpMock.expectOne(`${environment.apiUrl}/network/match?company=Acme%20Corp`);
    expect(req.request.method).toBe('GET');
    expect(req.request.params.get('company')).toBe('Acme Corp');
    req.flush({
      company_normalized: 'acme corp',
      contacts: [
        {
          first_name: 'Jane',
          last_name: 'Doe',
          company: 'Acme Corp',
          position: 'Engineer',
          linkedin_url: 'https://linkedin.com/in/janedoe',
          email: null,
          connected_on: '2025-01-15',
          company_normalized: 'acme corp',
        },
      ],
    });
  });
});
