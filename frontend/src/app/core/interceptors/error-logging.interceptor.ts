import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, throwError } from 'rxjs';
import { ErrorReportingService } from '../services/error-reporting.service';

/**
 * Taps every failed HTTP response into the central ErrorReportingService so
 * field debugging is no longer blind, then rethrows untouched. Component-level
 * error handlers (UI signals, etc.) still run exactly as before.
 *
 * Logging only — it must run AFTER the auth/error interceptors so any
 * recovery (e.g. 401 logout) has already happened by the time we observe the
 * error, and it never swallows the failure.
 */
export const errorLoggingInterceptor: HttpInterceptorFn = (req, next) => {
  const reporter = inject(ErrorReportingService);
  return next(req).pipe(
    catchError((err: unknown) => {
      reporter.report(err, {
        source: 'http',
        url: req.url,
        status: err instanceof HttpErrorResponse ? err.status : undefined,
        method: req.method,
      });
      return throwError(() => err);
    }),
  );
};
