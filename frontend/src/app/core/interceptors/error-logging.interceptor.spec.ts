import { TestBed } from '@angular/core/testing';
import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { errorLoggingInterceptor } from './error-logging.interceptor';
import { ErrorReportingService } from '../services/error-reporting.service';

describe('errorLoggingInterceptor', () => {
  const report = vi.fn();
  let http: HttpClient;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    report.mockReset();
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([errorLoggingInterceptor])),
        provideHttpClientTesting(),
        { provide: ErrorReportingService, useValue: { report } },
      ],
    });
    http = TestBed.inject(HttpClient);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('reports failed responses and rethrows to the caller', () => {
    let propagatedStatus: number | undefined;
    http.get('/api/widgets').subscribe({
      next: () => {
        throw new Error('expected the request to fail');
      },
      error: (e) => {
        propagatedStatus = e.status;
      },
    });

    const req = httpMock.expectOne('/api/widgets');
    expect(req.request.method).toBe('GET');
    req.flush('nope', { status: 500, statusText: 'Server Error' });

    // The error still reaches the component-level handler.
    expect(propagatedStatus).toBe(500);

    // And it was centrally reported with structured HTTP context.
    expect(report).toHaveBeenCalledTimes(1);
    const [err, context] = report.mock.calls[0];
    expect(err).toBeTruthy();
    expect(context).toMatchObject({
      source: 'http',
      url: '/api/widgets',
      status: 500,
      method: 'GET',
    });
  });

  it('does not report successful responses', () => {
    http.get('/api/widgets').subscribe();
    httpMock.expectOne('/api/widgets').flush({ ok: true });
    expect(report).not.toHaveBeenCalled();
  });
});
