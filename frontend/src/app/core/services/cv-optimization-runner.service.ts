import { Injectable, inject, signal } from '@angular/core';
import { Subject } from 'rxjs';
import { ApplicationsService } from './applications.service';
import { mapLlmError } from './llm-error.util';
import { ClaimReadiness } from '../../pages/applications/models/cv-optimization.model';

/**
 * Long-lived coordinator for CV optimization runs.
 *
 * Lives at the root injector so an in-flight generation survives the user
 * switching tabs (which destroys `cv-tab.component`). Tracks the running
 * application id so the button can be disabled on the originating tab and
 * fires `completed$` so the parent can refetch the aggregate from anywhere.
 */
@Injectable({ providedIn: 'root' })
export class CvOptimizationRunnerService {
  private service = inject(ApplicationsService);

  /** Application id currently being optimized, or null. */
  readonly runningId = signal<string | null>(null);
  /** Last error from the most recent run, surfaced to the originating tab. */
  readonly lastError = signal<string>('');
  private readinessByApplication = signal<Record<string, ClaimReadiness>>({});

  /** Emits the application id whose optimization just finished. */
  readonly completed$ = new Subject<string>();

  isRunning(applicationId: string): boolean {
    return this.runningId() === applicationId;
  }

  lastReadiness(applicationId: string): ClaimReadiness | null {
    return this.readinessByApplication()[applicationId] ?? null;
  }

  run(applicationId: string, cvLanguage: 'en' | 'es'): void {
    // Reject overlapping runs on the same application — the LLM call is
    // expensive and the resulting state would be ambiguous if two finished
    // out of order.
    if (this.runningId() === applicationId) return;
    this.runningId.set(applicationId);
    this.lastError.set('');
    this.readinessByApplication.update((current) =>
      Object.fromEntries(Object.entries(current).filter(([id]) => id !== applicationId)),
    );
    this.service.generateOptimization(applicationId, { cv_language: cvLanguage }).subscribe({
      next: (optimization) => {
        if (optimization.claim_readiness) {
          this.readinessByApplication.update((current) => ({
            ...current,
            [applicationId]: optimization.claim_readiness!,
          }));
        }
        this.runningId.set(null);
        this.completed$.next(applicationId);
      },
      error: (err) => {
        this.runningId.set(null);
        this.lastError.set(mapLlmError(err, 'Optimization failed'));
        this.completed$.next(applicationId);
      },
    });
  }
}
