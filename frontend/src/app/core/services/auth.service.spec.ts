import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { Router } from '@angular/router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AuthService } from './auth.service';
import { environment } from '../../../environments/environment';

function makeService(router: unknown = { navigate: () => {} }): {
  service: AuthService;
  httpMock: HttpTestingController;
} {
  TestBed.configureTestingModule({
    providers: [
      AuthService,
      provideHttpClient(),
      provideHttpClientTesting(),
      { provide: Router, useValue: router },
    ],
  });
  return {
    service: TestBed.inject(AuthService),
    httpMock: TestBed.inject(HttpTestingController),
  };
}

describe('AuthService', () => {
  afterEach(() => {
    TestBed.resetTestingModule();
  });

  it('starts unauthenticated with no cached session', () => {
    const { service, httpMock } = makeService();
    expect(service.isAuthenticated()).toBe(false);
    expect(service.role()).toBeNull();
    expect(service.isAdmin()).toBe(false);
    httpMock.verify();
  });

  it('never touches localStorage for the session', () => {
    const spy = vi.spyOn(Storage.prototype, 'setItem');
    const { service, httpMock } = makeService();
    service.login('admin', 'secret').subscribe();
    httpMock.expectOne(`${environment.apiUrl}/auth/login`).flush({ access_token: 't' });
    httpMock
      .expectOne(`${environment.apiUrl}/auth/me`)
      .flush({ username: 'admin', role: 'admin' });
    expect(spy).not.toHaveBeenCalled();
    spy.mockRestore();
    httpMock.verify();
  });

  it('ensureLoaded probes /auth/me and marks the session authenticated', () => {
    const { service, httpMock } = makeService();
    let ok: boolean | undefined;
    service.ensureLoaded().subscribe((r) => (ok = r));
    const req = httpMock.expectOne(`${environment.apiUrl}/auth/me`);
    expect(req.request.method).toBe('GET');
    req.flush({ username: 'admin', role: 'admin' });
    expect(ok).toBe(true);
    expect(service.isAuthenticated()).toBe(true);
    expect(service.role()).toBe('admin');
    expect(service.isAdmin()).toBe(true);
    httpMock.verify();
  });

  it('treats a 401 from /auth/me as anonymous', () => {
    const { service, httpMock } = makeService();
    let ok: boolean | undefined;
    service.ensureLoaded().subscribe((r) => (ok = r));
    httpMock
      .expectOne(`${environment.apiUrl}/auth/me`)
      .flush('nope', { status: 401, statusText: 'Unauthorized' });
    expect(ok).toBe(false);
    expect(service.isAuthenticated()).toBe(false);
    httpMock.verify();
  });

  it('caches the session probe so repeat ensureLoaded calls do not refetch', () => {
    const { service, httpMock } = makeService();
    service.ensureLoaded().subscribe();
    httpMock
      .expectOne(`${environment.apiUrl}/auth/me`)
      .flush({ username: 'admin', role: 'admin' });
    // Second call: state resolved, so no new request.
    let ok: boolean | undefined;
    service.ensureLoaded().subscribe((r) => (ok = r));
    httpMock.expectNone(`${environment.apiUrl}/auth/me`);
    expect(ok).toBe(true);
    httpMock.verify();
  });

  it('login posts credentials then hydrates the session from /auth/me', () => {
    const { service, httpMock } = makeService();
    let user: { username: string; role: string } | null | undefined;
    service.login('admin', 'secret').subscribe((u) => (user = u));

    const login = httpMock.expectOne(`${environment.apiUrl}/auth/login`);
    expect(login.request.method).toBe('POST');
    expect(login.request.body).toEqual({ username: 'admin', password: 'secret' });
    login.flush({ access_token: 't', token_type: 'bearer' });

    httpMock
      .expectOne(`${environment.apiUrl}/auth/me`)
      .flush({ username: 'admin', role: 'admin' });
    expect(user).toEqual({ username: 'admin', role: 'admin' });
    expect(service.isAuthenticated()).toBe(true);
    httpMock.verify();
  });

  it('logout posts /auth/logout, clears session, and routes to /login', () => {
    const navigate = vi.fn();
    const { service, httpMock } = makeService({ navigate });
    // Seed an authenticated session first.
    service.ensureLoaded().subscribe();
    httpMock
      .expectOne(`${environment.apiUrl}/auth/me`)
      .flush({ username: 'admin', role: 'admin' });
    expect(service.isAuthenticated()).toBe(true);

    service.logout();
    const req = httpMock.expectOne(`${environment.apiUrl}/auth/logout`);
    expect(req.request.method).toBe('POST');
    req.flush({ detail: 'logged out' });

    expect(service.isAuthenticated()).toBe(false);
    expect(navigate).toHaveBeenCalledWith(['/login']);
    httpMock.verify();
  });
});
