import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, throwError } from 'rxjs';
import { AuthService } from '../services/auth.service';

/**
 * Recovers from a rejected session. A 401 from a normal API call means the
 * session cookie is missing, expired, or invalid, so clear session state and
 * bounce to /login instead of leaving the user stranded on silent 401s.
 *
 * The auth endpoints are exempt: /auth/login's 401 is "bad credentials" (handled
 * inline by the login form), and /auth/me and /auth/logout are the session-probe
 * and teardown calls the AuthService already handles — routing their 401s here
 * would double-handle them (and could bounce anonymous users mid-probe).
 */
export const errorInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthService);
  return next(req).pipe(
    catchError((error: HttpErrorResponse) => {
      if (error.status === 401 && !isAuthEndpoint(req.url)) {
        auth.logout();
      }
      return throwError(() => error);
    }),
  );
};

function isAuthEndpoint(url: string): boolean {
  return url.includes('/auth/login') || url.includes('/auth/me') || url.includes('/auth/logout');
}
