import { describe, it, expect, beforeEach } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { ResearchService } from './research.service';
import { environment } from '../../../environments/environment';

describe('ResearchService', () => {
  let service: ResearchService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(ResearchService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  it('GETs research by company name', () => {
    service.get('BC Tecnología').subscribe();
    const req = httpMock.expectOne(`${environment.apiUrl}/research/BC%20Tecnolog%C3%ADa`);
    expect(req.request.method).toBe('GET');
    req.flush({});
  });
});
