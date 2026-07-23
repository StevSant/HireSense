import {
  HttpErrorResponse,
  HttpEvent,
  HttpHandlerFn,
  HttpInterceptorFn,
  HttpRequest,
  HttpResponse,
} from '@angular/common/http';
import { Observable, of, throwError } from 'rxjs';
import {
  demoApplicationMatch,
  demoApplication,
  demoApplications,
  demoComp,
  demoFunnel,
  demoFocus,
  demoJobs,
  demoJobsPage,
  demoMarket,
  demoPortfolioEngagement,
  demoProfile,
  demoSkillGap,
} from './demo-fixtures';

const demoOrigin = 'https://demo.hiresense.app';
const readOnlyMessage =
  'This public HireSense demo is read-only. Explore the prepared data or run the repository locally to use this action.';

export const demoApiInterceptor: HttpInterceptorFn = (
  request: HttpRequest<unknown>,
  next: HttpHandlerFn,
): Observable<HttpEvent<unknown>> => {
  if (!request.url.startsWith('/api')) {
    return next(request);
  }

  const path = new URL(request.urlWithParams, demoOrigin).pathname;
  const response = demoResponse(request.method, path);

  if (response !== undefined) {
    return of(new HttpResponse({ status: 200, body: response, url: request.urlWithParams }));
  }

  if (request.method !== 'GET') {
    return throwError(
      () =>
        new HttpErrorResponse({
          status: 403,
          statusText: 'Read-only demo',
          url: request.urlWithParams,
          error: { detail: readOnlyMessage },
        }),
    );
  }

  return throwError(
    () =>
      new HttpErrorResponse({
        status: 404,
        statusText: 'Demo fixture not found',
        url: request.urlWithParams,
        error: { detail: 'This screen is not included in the public demo journey.' },
      }),
  );
};

function demoResponse(method: string, path: string): unknown | undefined {
  if (method === 'GET' && path === '/api/auth/me') {
    return { username: 'demo.candidate', role: 'user' };
  }
  if (method === 'GET' && path === '/api/ingestion/jobs') {
    return demoJobsPage;
  }
  if (method === 'GET' && path.startsWith('/api/ingestion/jobs/')) {
    const jobId = path.split('/').at(-1);
    return demoJobs.find((job) => job.id === jobId);
  }
  if (method === 'GET' && path === '/api/applications') {
    return demoApplications;
  }
  if (method === 'GET' && path === '/api/applications/demo-app-1') {
    return demoApplication;
  }
  if (method === 'GET' && path === '/api/analytics/funnel') {
    return demoFunnel;
  }
  if (method === 'GET' && path === '/api/analytics/market') {
    return demoMarket;
  }
  if (method === 'GET' && path === '/api/analytics/skill-gap') {
    return demoSkillGap;
  }
  if (method === 'GET' && path === '/api/analytics/comp') {
    return demoComp;
  }
  if (method === 'GET' && path === '/api/analytics/focus') {
    return demoFocus;
  }
  if (method === 'GET' && path === '/api/portfolio/engagement') {
    return demoPortfolioEngagement;
  }
  if (method === 'GET' && path === '/api/profile/list') {
    return [demoProfile];
  }
  if (method === 'GET' && path === '/api/profile/current') {
    return demoProfile;
  }
  if (method === 'GET' && path === '/api/ingestion/portals') {
    return [];
  }
  if (method === 'POST' && path === '/api/applications/demo-app-1/match') {
    return demoApplicationMatch;
  }
  return undefined;
}
