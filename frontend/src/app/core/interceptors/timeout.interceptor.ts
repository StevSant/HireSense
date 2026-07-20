import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { catchError, throwError, timeout, TimeoutError } from 'rxjs';
import { environment } from '../../../environments/environment';

// URL patterns for LLM-backed endpoints, which can legitimately run far
// longer than a normal CRUD call (external model latency, prompt size).
// Every pattern requires a segment boundary after the literal text so a
// prefix never accidentally swallows an unrelated route (e.g. bare
// `/cover-letter` must not match the CRUD `/cover-letter-templates` routes).
const LLM_SLOW_URL_PATTERNS: RegExp[] = [
  /\/interview\/prepare(?:$|[/?])/,
  /\/research(?:$|[/?])/,
  /\/optimization(?:$|[/?])/,
  /\/cover-letter(?:$|[/?])/,
  /\/matching\/analyze(?:$|[/?])/,
  /\/matching\/evaluate(?:$|[/?])/,
  // tracking.service.batchEvaluate() posts here.
  /\/matching\/batch-evaluate(?:$|[/?])/,
  /\/outreach\/generate(?:$|[/?])/,
  /\/applications\/[^/?]+\/(?:match|optimize|interview-prep|cover-letter)(?:$|[/?])/,
  /\/profile\/translate(?:$|[/?])/,
  /\/profile\/upload-file(?:$|[/?])/,
];

function isLlmSlowUrl(url: string): boolean {
  return LLM_SLOW_URL_PATTERNS.some((pattern) => pattern.test(url));
}

/**
 * Bounds every HTTP request so a hung call — most commonly a slow LLM
 * generation — can't spin a loading spinner forever. LLM-backed endpoints get
 * `environment.httpTimeoutLlmMs`; everything else gets the shorter
 * `environment.httpTimeoutMs`. On expiry, emits a synthetic 408
 * HttpErrorResponse so the existing `err.error?.detail` / `err.status`
 * handling in components and `mapLlmError` renders it like any other failed
 * request instead of needing a separate TimeoutError code path.
 *
 * Must be registered LAST in `withInterceptors([...])` (closest to the
 * backend) — see the ordering comment in app.config.ts. Any earlier and the
 * synthetic 408 this throws would bypass errorLoggingInterceptor's
 * catchError entirely, so client-side timeouts would never reach
 * ErrorReportingService/telemetry.
 */
export const timeoutInterceptor: HttpInterceptorFn = (req, next) => {
  const ms = isLlmSlowUrl(req.url) ? environment.httpTimeoutLlmMs : environment.httpTimeoutMs;
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
