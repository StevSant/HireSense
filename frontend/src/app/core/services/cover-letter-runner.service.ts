import { Injectable, inject, signal } from '@angular/core';
import { Subject } from 'rxjs';
import { CoverLetterTone } from '../../pages/applications/models/cover-letter-tone.model';
import { ApplicationsService } from './applications.service';
import { mapLlmError } from './llm-error.util';

/**
 * Long-lived coordinator for cover-letter generation runs.
 *
 * Mirrors {@link CvOptimizationRunnerService} so an in-flight generation
 * survives the user switching tabs (which destroys `apply-tab.component`).
 * Exposes a per-application `running` flag and a `completed$` stream the
 * detail page subscribes to in order to refetch the aggregate.
 */
@Injectable({ providedIn: 'root' })
export class CoverLetterRunnerService {
  private service = inject(ApplicationsService);

  readonly runningId = signal<string | null>(null);
  readonly lastError = signal<string>('');

  readonly completed$ = new Subject<string>();

  isRunning(applicationId: string): boolean {
    return this.runningId() === applicationId;
  }

  run(applicationId: string, cvLanguage: 'en' | 'es', tone: CoverLetterTone): void {
    if (this.runningId() === applicationId) return;
    this.runningId.set(applicationId);
    this.lastError.set('');
    this.service.generateCoverLetter(applicationId, { cv_language: cvLanguage, tone }).subscribe({
      next: () => {
        this.runningId.set(null);
        this.completed$.next(applicationId);
      },
      error: (err) => {
        this.runningId.set(null);
        this.lastError.set(mapLlmError(err, 'Cover letter generation failed'));
        this.completed$.next(applicationId);
      },
    });
  }
}
