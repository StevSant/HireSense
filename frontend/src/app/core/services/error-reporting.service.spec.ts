import { TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ErrorReportingService } from './error-reporting.service';

describe('ErrorReportingService', () => {
  let service: ErrorReportingService;
  let consoleSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [ErrorReportingService] });
    service = TestBed.inject(ErrorReportingService);
    consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => undefined);
  });

  afterEach(() => consoleSpy.mockRestore());

  it('console.errors a structured report with message and context', () => {
    const err = new Error('boom');
    service.report(err, { source: 'http', status: 500 });

    expect(consoleSpy).toHaveBeenCalledTimes(1);
    const [, report] = consoleSpy.mock.calls[0];
    expect(report).toMatchObject({
      message: 'boom',
      context: { source: 'http', status: 500 },
      error: err,
    });
  });

  it('reports without context', () => {
    service.report('plain string failure');
    const [, report] = consoleSpy.mock.calls[0];
    expect(report).toMatchObject({ message: 'plain string failure', context: undefined });
  });

  it('forwards the report to a registered sink', () => {
    const sink = vi.fn();
    service.setSink(sink);
    const err = new Error('boom');
    service.report(err, { source: 'uncaught' });

    expect(sink).toHaveBeenCalledTimes(1);
    expect(sink.mock.calls[0][0]).toMatchObject({
      message: 'boom',
      context: { source: 'uncaught' },
      error: err,
    });
  });
});
