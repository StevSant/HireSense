import { Injectable } from '@angular/core';
import { environment } from '../../../environments/environment';

/**
 * Structured shape forwarded to any downstream sink (console today,
 * OTel / a browser error tracker tomorrow).
 */
export interface ErrorReport {
  message: string;
  context?: Record<string, unknown>;
  error: unknown;
}

/** Pluggable downstream sink. The extension seam for OTel / a tracker. */
export type ErrorSink = (report: ErrorReport) => void;

/**
 * Central place every uncaught error and failed HTTP response flows through.
 *
 * Today it just `console.error`s a structured payload so field debugging is
 * no longer blind. The `setSink()` hook is the deliberate extension seam: an
 * OTel exporter or browser error tracker can be registered later (e.g. from a
 * bootstrap provider) without touching the global handler or the interceptor.
 */
@Injectable({ providedIn: 'root' })
export class ErrorReportingService {
  /** Defaults to a no-op; swap in an OTel/tracker forwarder via setSink(). */
  private sink: ErrorSink = () => {
    /* no-op until a tracker is wired in */
  };

  /** Register the downstream forwarder (OTel exporter, browser tracker, …). */
  setSink(sink: ErrorSink): void {
    this.sink = sink;
  }

  report(error: unknown, context?: Record<string, unknown>): void {
    const report: ErrorReport = {
      message: this.toMessage(error),
      context,
      error,
    };
    console.error('[HireSense]', report);
    this.forward(report);
  }

  /** Hand the report to the registered sink. Swallows sink failures. */
  private forward(report: ErrorReport): void {
    try {
      this.sink(report);
    } catch {
      // A broken tracker must never break the app or recurse into report().
      if (!environment.production) {
        console.error('[HireSense] error sink threw while forwarding a report');
      }
    }
  }

  private toMessage(error: unknown): string {
    if (error instanceof Error) {
      return error.message;
    }
    if (typeof error === 'string') {
      return error;
    }
    if (error && typeof error === 'object' && 'message' in error) {
      return String((error as { message: unknown }).message);
    }
    return 'Unknown error';
  }
}
