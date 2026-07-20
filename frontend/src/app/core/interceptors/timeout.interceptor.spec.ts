import { TestBed } from '@angular/core/testing';
import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { timeoutInterceptor } from './timeout.interceptor';
import { errorLoggingInterceptor } from './error-logging.interceptor';
import { ErrorReportingService } from '../services/error-reporting.service';
import { environment } from '../../../environments/environment';

describe('timeoutInterceptor', () => {
  let http: HttpClient;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    vi.useFakeTimers();
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([timeoutInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    http = TestBed.inject(HttpClient);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
    vi.useRealTimers();
  });

  it('emits a synthetic 408 when a default-timeout request hangs past httpTimeoutMs', () => {
    let captured: unknown;
    http.get('/api/ingestion/jobs').subscribe({
      next: () => {
        throw new Error('expected the request to time out');
      },
      error: (e) => {
        captured = e;
      },
    });

    const req = httpMock.expectOne('/api/ingestion/jobs');
    vi.advanceTimersByTime(environment.httpTimeoutMs);

    expect(req.cancelled).toBe(true);
    expect(captured).toMatchObject({ status: 408, error: { detail: 'Request timed out' } });
  });

  it('does not time out a default-timeout request that resolves before httpTimeoutMs', () => {
    let received: unknown;
    http.get('/api/ingestion/jobs').subscribe((res) => {
      received = res;
    });

    vi.advanceTimersByTime(environment.httpTimeoutMs - 1);
    httpMock.expectOne('/api/ingestion/jobs').flush({ ok: true });

    expect(received).toEqual({ ok: true });
  });

  it('does not time out an LLM-slow request before httpTimeoutLlmMs elapses', () => {
    let received: unknown;
    http.post('/api/interview/prepare', {}).subscribe((res) => {
      received = res;
    });

    // Past the default budget but still under the LLM budget.
    vi.advanceTimersByTime(environment.httpTimeoutMs + 1000);
    const req = httpMock.expectOne('/api/interview/prepare');
    expect(req.cancelled).toBeFalsy();
    req.flush({ ok: true });

    expect(received).toEqual({ ok: true });
  });

  it.each([
    '/api/interview/prepare',
    '/api/research',
    '/api/research/refresh',
    '/api/optimization/optimize',
    '/api/matching/analyze',
    '/api/matching/evaluate',
    '/api/matching/batch-evaluate',
    '/api/outreach/generate',
    '/api/applications/app-1/match',
    '/api/applications/app-1/optimize',
    '/api/applications/app-1/interview-prep',
    '/api/applications/app-1/cover-letter',
    '/api/profile/translate',
    '/api/profile/upload-file',
  ])('gives %s the LLM timeout budget, not the default one', (url) => {
    let captured: unknown;
    http.post(url, {}).subscribe({
      next: () => {
        throw new Error('expected the request to time out');
      },
      error: (e) => {
        captured = e;
      },
    });

    // Past the default budget: must still be alive.
    vi.advanceTimersByTime(environment.httpTimeoutMs + 1000);
    const req = httpMock.expectOne(url);
    expect(req.cancelled).toBeFalsy();

    // Past the LLM budget: now it must time out.
    vi.advanceTimersByTime(environment.httpTimeoutLlmMs);
    expect(req.cancelled).toBe(true);
    expect(captured).toMatchObject({ status: 408 });
  });

  it('does not misclassify the CRUD cover-letter-templates routes as LLM-slow', () => {
    let captured: unknown;
    http.get('/api/cover-letter-templates').subscribe({
      next: () => {
        throw new Error('expected the request to time out');
      },
      error: (e) => {
        captured = e;
      },
    });

    vi.advanceTimersByTime(environment.httpTimeoutMs);
    expect(httpMock.expectOne('/api/cover-letter-templates').cancelled).toBe(true);
    expect(captured).toMatchObject({ status: 408 });
  });

  it('passes through a real (non-timeout) HTTP error unchanged', () => {
    let captured: unknown;
    http.get('/api/ingestion/jobs').subscribe({
      next: () => {
        throw new Error('expected the request to fail');
      },
      error: (e) => {
        captured = e;
      },
    });

    httpMock
      .expectOne('/api/ingestion/jobs')
      .flush('nope', { status: 500, statusText: 'Server Error' });

    expect(captured).toMatchObject({ status: 500 });
  });
});

describe('timeoutInterceptor registered before errorLoggingInterceptor (telemetry path)', () => {
  // Pins the app.config.ts ordering contract: timeoutInterceptor must sit
  // LAST in withInterceptors([...]) (closest to the backend) so the synthetic
  // 408 it throws on expiry still flows back up through
  // errorLoggingInterceptor's catchError and reaches ErrorReportingService.
  // Reproduces that relative order here: errorLogging wraps timeout, exactly
  // like in app.config.ts.
  let http: HttpClient;
  let httpMock: HttpTestingController;
  const report = vi.fn();

  beforeEach(() => {
    vi.useFakeTimers();
    report.mockReset();
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([errorLoggingInterceptor, timeoutInterceptor])),
        provideHttpClientTesting(),
        { provide: ErrorReportingService, useValue: { report } },
      ],
    });
    http = TestBed.inject(HttpClient);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
    vi.useRealTimers();
  });

  it('reports the synthetic 408 to ErrorReportingService when a request times out', () => {
    let captured: unknown;
    http.get('/api/ingestion/jobs').subscribe({
      next: () => {
        throw new Error('expected the request to time out');
      },
      error: (e) => {
        captured = e;
      },
    });

    const req = httpMock.expectOne('/api/ingestion/jobs');
    vi.advanceTimersByTime(environment.httpTimeoutMs);

    expect(req.cancelled).toBe(true);
    expect(captured).toMatchObject({ status: 408 });
    expect(report).toHaveBeenCalledTimes(1);
    const [reportedErr, context] = report.mock.calls[0];
    expect(reportedErr).toMatchObject({ status: 408 });
    expect(context).toMatchObject({
      source: 'http',
      url: '/api/ingestion/jobs',
      status: 408,
      method: 'GET',
    });
  });

  it('still reports normal (non-timeout) HTTP errors', () => {
    let captured: unknown;
    http.get('/api/ingestion/jobs').subscribe({
      next: () => {
        throw new Error('expected the request to fail');
      },
      error: (e) => {
        captured = e;
      },
    });

    httpMock
      .expectOne('/api/ingestion/jobs')
      .flush('nope', { status: 500, statusText: 'Server Error' });

    expect(captured).toMatchObject({ status: 500 });
    expect(report).toHaveBeenCalledTimes(1);
    expect(report.mock.calls[0][1]).toMatchObject({ status: 500 });
  });
});
