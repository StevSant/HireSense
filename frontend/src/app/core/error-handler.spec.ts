import { TestBed } from '@angular/core/testing';
import { ErrorHandler } from '@angular/core';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { GlobalErrorHandler } from './error-handler';
import { ErrorReportingService } from './services/error-reporting.service';

describe('GlobalErrorHandler', () => {
  const report = vi.fn();
  let handler: ErrorHandler;

  beforeEach(() => {
    report.mockReset();
    TestBed.configureTestingModule({
      providers: [
        { provide: ErrorHandler, useClass: GlobalErrorHandler },
        { provide: ErrorReportingService, useValue: { report } },
      ],
    });
    handler = TestBed.inject(ErrorHandler);
  });

  it('delegates uncaught errors to the reporter with source=uncaught', () => {
    const err = new Error('kaboom');
    handler.handleError(err);
    expect(report).toHaveBeenCalledTimes(1);
    expect(report).toHaveBeenCalledWith(err, { source: 'uncaught' });
  });
});
