import { ErrorHandler, Injectable, inject } from '@angular/core';
import { ErrorReportingService } from './services/error-reporting.service';

/**
 * Global Angular error handler. Routes every uncaught error through the
 * central ErrorReportingService so nothing slips past unlogged, then defers
 * to the framework's default rethrow behavior by re-throwing.
 */
@Injectable()
export class GlobalErrorHandler implements ErrorHandler {
  private readonly reporter = inject(ErrorReportingService);

  handleError(error: unknown): void {
    this.reporter.report(error, { source: 'uncaught' });
  }
}
