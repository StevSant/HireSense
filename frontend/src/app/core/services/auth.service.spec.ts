import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { Router } from '@angular/router';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { AuthService } from './auth.service';
import { environment } from '../../../environments/environment';

function makeToken(claims: Record<string, unknown>): string {
  const future = Math.floor(Date.now() / 1000) + 3600;
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }));
  const payload = btoa(JSON.stringify({ exp: future, ...claims }));
  return `${header}.${payload}.signature`;
}

function makeService(): { service: AuthService; httpMock: HttpTestingController } {
  TestBed.configureTestingModule({
    providers: [
      AuthService,
      provideHttpClient(),
      provideHttpClientTesting(),
      { provide: Router, useValue: { navigate: () => {} } },
    ],
  });
  return {
    service: TestBed.inject(AuthService),
    httpMock: TestBed.inject(HttpTestingController),
  };
}

describe('AuthService', () => {
  afterEach(() => {
    localStorage.clear();
    TestBed.resetTestingModule();
  });

  it('exposes role and isAdmin from an admin token', () => {
    localStorage.setItem('access_token', makeToken({ sub: 'admin', role: 'admin' }));
    const { service, httpMock } = makeService();
    expect(service.role()).toBe('admin');
    expect(service.isAdmin()).toBe(true);
    httpMock.verify();
  });

  it('reports a non-admin token as not admin', () => {
    localStorage.setItem('access_token', makeToken({ sub: 'bob', role: 'member' }));
    const { service, httpMock } = makeService();
    expect(service.role()).toBe('member');
    expect(service.isAdmin()).toBe(false);
    httpMock.verify();
  });

  it('has a null role when no token is stored', () => {
    const { service, httpMock } = makeService();
    expect(service.role()).toBeNull();
    expect(service.isAdmin()).toBe(false);
    httpMock.verify();
  });

  it('me() GETs /auth/me', () => {
    const { service, httpMock } = makeService();
    service.me().subscribe();
    const req = httpMock.expectOne(`${environment.apiUrl}/auth/me`);
    expect(req.request.method).toBe('GET');
    req.flush({ username: 'admin', role: 'admin' });
    httpMock.verify();
  });
});
