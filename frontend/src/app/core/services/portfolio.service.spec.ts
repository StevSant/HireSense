import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { PortfolioService } from './portfolio.service';
import { environment } from '../../../environments/environment';

describe('PortfolioService', () => {
  let service: PortfolioService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(PortfolioService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('lists projects', () => {
    service.listProjects().subscribe((res) => {
      expect(res.projects.length).toBe(1);
      expect(res.last_synced_at).toBe('2026-06-09T00:00:00Z');
    });
    const req = httpMock.expectOne(`${environment.apiUrl}/portfolio/projects`);
    expect(req.request.method).toBe('GET');
    req.flush({
      projects: [
        {
          id: 'p1', source: 'supabase', source_key: 'hiresense', url: null, demo_url: null,
          pinned: true, position: 1, tech: ['python'],
          translations: { en: { title: 'HireSense', description: 'AI job hunting' } },
        },
      ],
      last_synced_at: '2026-06-09T00:00:00Z',
    });
  });

  it('triggers a sync', () => {
    service.sync().subscribe((res) => expect(res.counts_by_source['supabase']).toBe(3));
    const req = httpMock.expectOne(`${environment.apiUrl}/portfolio/sync`);
    expect(req.request.method).toBe('POST');
    req.flush({ counts_by_source: { supabase: 3 }, errors: {}, synced_at: '2026-06-09T00:00:00Z' });
  });
});
