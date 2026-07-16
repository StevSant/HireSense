import { TestBed } from '@angular/core/testing';
import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { timeoutInterceptor } from './timeout.interceptor';
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

    httpMock.expectOne('/api/ingestion/jobs').flush('nope', { status: 500, statusText: 'Server Error' });

    expect(captured).toMatchObject({ status: 500 });
  });
});
