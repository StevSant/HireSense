import { TestBed } from '@angular/core/testing';
import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { afterEach, describe, expect, it } from 'vitest';
import { credentialsInterceptor } from './credentials.interceptor';
import { environment } from '../../../environments/environment';

function setup(): { http: HttpClient; httpMock: HttpTestingController } {
  TestBed.configureTestingModule({
    providers: [
      provideHttpClient(withInterceptors([credentialsInterceptor])),
      provideHttpClientTesting(),
    ],
  });
  return {
    http: TestBed.inject(HttpClient),
    httpMock: TestBed.inject(HttpTestingController),
  };
}

describe('credentialsInterceptor', () => {
  afterEach(() => TestBed.resetTestingModule());

  it('sends withCredentials for API-base requests', () => {
    const { http, httpMock } = setup();
    http.get(`${environment.apiUrl}/auth/me`).subscribe();
    const req = httpMock.expectOne(`${environment.apiUrl}/auth/me`);
    expect(req.request.withCredentials).toBe(true);
    req.flush({});
    httpMock.verify();
  });

  it('does not attach credentials to non-API (third-party) URLs', () => {
    const { http, httpMock } = setup();
    http.get('https://third-party.example.com/data').subscribe();
    const req = httpMock.expectOne('https://third-party.example.com/data');
    expect(req.request.withCredentials).toBe(false);
    req.flush({});
    httpMock.verify();
  });
});
