import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { FeedbackKind } from '@core/contracts/feedback-kind.model';
import { FeedbackSignal } from '@core/contracts/feedback-signal.model';
import { PreferenceExplanation } from '@core/contracts/preference-explanation.model';

@Injectable({ providedIn: 'root' })
export class PreferenceService {
  constructor(private http: HttpClient) {}

  /** `jobId` must be a UUID string; the backend rejects non-UUID values with HTTP 422. */
  submitFeedback(jobId: string, kind: FeedbackKind): Observable<FeedbackSignal> {
    return this.http.post<FeedbackSignal>(`${environment.apiUrl}/preference/feedback`, {
      job_id: jobId,
      kind,
    });
  }

  explain(): Observable<PreferenceExplanation> {
    return this.http.get<PreferenceExplanation>(`${environment.apiUrl}/preference/explain`);
  }

  signals(): Observable<FeedbackSignal[]> {
    return this.http.get<FeedbackSignal[]>(`${environment.apiUrl}/preference/signals`);
  }

  reset(): Observable<void> {
    return this.http.post<void>(`${environment.apiUrl}/preference/reset`, {});
  }
}
