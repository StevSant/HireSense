import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { catchError, throwError, timeout, TimeoutError } from 'rxjs';
import { timeoutClassForUrl } from '@core/api';
import { environment } from '@env/environment';

/**
 * Bounds every HTTP request so a hung call — most commonly a slow LLM
 * generation — can't spin a loading spinner forever. Which endpoints are slow
 * is not restated here: it is read off the route table in `@core/api`, so a
 * newly added endpoint gets its timeout from the same declaration the services
 * build their URLs from, instead of from a parallel list that has to be
 * remembered. Only the budgets themselves live here, in `environment`.
 *
 * On expiry, emits a synthetic 408 HttpErrorResponse so the existing
 * `err.error?.detail` / `err.status` handling in components and `mapLlmError`
 * renders it like any other failed request instead of needing a separate
 * TimeoutError code path.
 *
 * Must be registered LAST in `withInterceptors([...])` (closest to the
 * backend) — see the ordering comment in app.config.ts. Any earlier and the
 * synthetic 408 this throws would bypass errorLoggingInterceptor's
 * catchError entirely, so client-side timeouts would never reach
 * ErrorReportingService/telemetry.
 */
export const timeoutInterceptor: HttpInterceptorFn = (req, next) => {
  const ms = timeoutMsFor(req.url);
  return next(req).pipe(
    timeout(ms),
    catchError((error: unknown) => {
      if (error instanceof TimeoutError) {
        return throwError(
          () =>
            new HttpErrorResponse({
              status: 408,
              statusText: 'Request Timeout',
              url: req.url,
              error: { detail: 'Request timed out' },
            }),
        );
      }
      return throwError(() => error);
    }),
  );
};

function timeoutMsFor(url: string): number {
  switch (timeoutClassForUrl(url)) {
    // A full source pass legitimately runs for minutes while external boards
    // are paged and enriched.
    case 'fetch':
      return environment.httpTimeoutFetchMs;
    // External model latency legitimately exceeds the default budget.
    case 'llm':
      return environment.httpTimeoutLlmMs;
    default:
      return environment.httpTimeoutMs;
  }
}
