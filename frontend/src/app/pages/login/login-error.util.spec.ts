import { HttpErrorResponse } from '@angular/common/http';
import { describe, expect, it } from 'vitest';
import { mapLoginError } from './login-error.util';

function httpError(status: number, detail?: string): HttpErrorResponse {
  return new HttpErrorResponse({
    status,
    url: '/api/auth/login',
    error: detail ? { detail } : null,
  });
}

describe('mapLoginError', () => {
  it('names a rejected credential on 401', () => {
    expect(mapLoginError(httpError(401, 'Invalid credentials'))).toBe(
      'Incorrect username or password.',
    );
  });

  it('distinguishes rate limiting from a bad password on 429', () => {
    expect(mapLoginError(httpError(429, 'Too many login attempts'))).toBe(
      'Too many login attempts — wait a few minutes and try again.',
    );
  });

  it('reports an unconfigured server on 503', () => {
    expect(mapLoginError(httpError(503, 'Identity not configured'))).toBe(
      'Sign-in is not configured on the server.',
    );
  });

  it('reports the synthetic timeout status', () => {
    expect(mapLoginError(httpError(408))).toBe('The server took too long to respond. Try again.');
  });

  it('reports an unreachable backend on status 0', () => {
    expect(mapLoginError(httpError(0))).toBe(
      'Cannot reach the server — check that the backend is running.',
    );
  });

  it('falls back to the server detail for an unmapped status', () => {
    expect(mapLoginError(httpError(500, 'boom'))).toBe('boom');
  });

  it('names the status when an unmapped response carries no detail', () => {
    expect(mapLoginError(httpError(418))).toBe('Sign-in failed (HTTP 418).');
  });

  it('handles a non-HTTP error without pretending the password was wrong', () => {
    expect(mapLoginError(new Error('kaboom'))).toBe(
      'Sign-in failed unexpectedly — see the browser console for details.',
    );
  });
});
