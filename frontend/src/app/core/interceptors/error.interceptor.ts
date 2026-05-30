import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, throwError } from 'rxjs';
import { AuthService } from '../services/auth.service';

/**
 * Recovers from a rejected token. A 401 from any API call (other than the
 * login attempt itself) means the stored token is stale, expired, or invalid,
 * so clear it and bounce to /login instead of leaving the user stranded on
 * silent 401s. The login request is exempt — its 401 means "bad credentials"
 * and is handled inline by the login form.
 */
export const errorInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthService);
  return next(req).pipe(
    catchError((error: HttpErrorResponse) => {
      if (error.status === 401 && !req.url.includes('/auth/login')) {
        auth.logout();
      }
      return throwError(() => error);
    }),
  );
};
