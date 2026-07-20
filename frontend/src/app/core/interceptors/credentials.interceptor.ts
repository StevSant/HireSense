import { HttpInterceptorFn } from '@angular/common/http';
import { environment } from '../../../environments/environment';

/**
 * Attaches the httpOnly session cookie to API calls by setting `withCredentials`.
 * Scoped to the API base (never a blanket `withCredentials`) so the session
 * cookie is never offered to third-party origins a request might target.
 */
export const credentialsInterceptor: HttpInterceptorFn = (req, next) => {
  if (isApiUrl(req.url)) {
    req = req.clone({ withCredentials: true });
  }
  return next(req);
};

function isApiUrl(url: string): boolean {
  return url.startsWith(environment.apiUrl);
}
