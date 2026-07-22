import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { environment } from '../../../environments/environment';
import { AuthService } from '../services/auth.service';
import { errorInterceptor } from './error.interceptor';

describe('errorInterceptor', () => {
  const logout = vi.fn();
  let http: HttpClient;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([errorInterceptor])),
        provideHttpClientTesting(),
        { provide: AuthService, useValue: { logout } },
      ],
    });

    http = TestBed.inject(HttpClient);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
    TestBed.resetTestingModule();
    vi.clearAllMocks();
  });

  it('logs out once and rethrows a 401 from a non-auth endpoint', () => {
    const url = `${environment.apiUrl}/applications`;
    let capturedError: unknown;

    http.get(url).subscribe({ error: (error: unknown) => (capturedError = error) });
    httpMock.expectOne(url).flush({}, { status: 401, statusText: 'Unauthorized' });

    expect(logout).toHaveBeenCalledTimes(1);
    expect(capturedError).toMatchObject({ status: 401 });
  });

  it.each(['/auth/login', '/auth/me', '/auth/logout'])(
    'skips logout and rethrows a 401 from %s',
    (path) => {
      const url = `${environment.apiUrl}${path}`;
      let capturedError: unknown;

      http.get(url).subscribe({ error: (error: unknown) => (capturedError = error) });
      httpMock.expectOne(url).flush({}, { status: 401, statusText: 'Unauthorized' });

      expect(logout).not.toHaveBeenCalled();
      expect(capturedError).toMatchObject({ status: 401 });
    },
  );

  it('does not exempt a protected endpoint whose query contains an auth path', () => {
    const url = `${environment.apiUrl}/applications?next=/auth/login`;

    http.get(url).subscribe({ error: () => undefined });
    httpMock.expectOne(url).flush({}, { status: 401, statusText: 'Unauthorized' });

    expect(logout).toHaveBeenCalledTimes(1);
  });

  it('skips logout and rethrows a non-401 response', () => {
    const url = `${environment.apiUrl}/applications`;
    let capturedError: unknown;

    http.get(url).subscribe({ error: (error: unknown) => (capturedError = error) });
    httpMock.expectOne(url).flush({}, { status: 500, statusText: 'Internal Server Error' });

    expect(logout).not.toHaveBeenCalled();
    expect(capturedError).toMatchObject({ status: 500 });
  });
});
