import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiClient, API_ROUTES } from '@core/api';
import { FeedbackKind } from '@core/contracts/feedback-kind.model';
import { FeedbackSignal } from '@core/contracts/feedback-signal.model';
import { PreferenceExplanation } from '@core/contracts/preference-explanation.model';

@Injectable({ providedIn: 'root' })
export class PreferenceService {
  constructor(private api: ApiClient) {}

  /** `jobId` must be a UUID string; the backend rejects non-UUID values with HTTP 422. */
  submitFeedback(jobId: string, kind: FeedbackKind): Observable<FeedbackSignal> {
    return this.api.post<FeedbackSignal>(API_ROUTES.preference.feedback(), {
      job_id: jobId,
      kind,
    });
  }

  explain(): Observable<PreferenceExplanation> {
    return this.api.get<PreferenceExplanation>(API_ROUTES.preference.explain());
  }

  signals(): Observable<FeedbackSignal[]> {
    return this.api.get<FeedbackSignal[]>(API_ROUTES.preference.signals());
  }

  reset(): Observable<void> {
    return this.api.post<void>(API_ROUTES.preference.reset(), {});
  }
}
