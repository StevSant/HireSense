import { HttpErrorResponse } from '@angular/common/http';

/**
 * Message mapping for a failed sign-in. Every failure used to render as
 * "Invalid credentials", which hid the cases that have nothing to do with the
 * password: 429 from the login rate limiter (5 attempts / 15 min), 503 when the
 * backend has no admin credentials configured, 408 from the timeout
 * interceptor, and status 0 when the API is unreachable. Unmapped statuses fall
 * back to the server's `detail`, then to the status itself, so a surprising
 * failure is still identifiable from the UI instead of being misattributed.
 */
export function mapLoginError(err: unknown): string {
  if (!(err instanceof HttpErrorResponse)) {
    return 'Sign-in failed unexpectedly — see the browser console for details.';
  }
  switch (err.status) {
    case 0:
      return 'Cannot reach the server — check that the backend is running.';
    case 401:
      return 'Incorrect username or password.';
    case 408:
      return 'The server took too long to respond. Try again.';
    case 429:
      return 'Too many login attempts — wait a few minutes and try again.';
    case 503:
      return 'Sign-in is not configured on the server.';
    default:
      return err.error?.detail || `Sign-in failed (HTTP ${err.status}).`;
  }
}
