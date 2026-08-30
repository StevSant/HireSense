import { HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiClient, API_ROUTES } from '@core/api';
import {
  SubmissionAttempt,
  SubmissionEvent,
  SubmissionStatus,
} from '@core/contracts/submission.model';

@Injectable({ providedIn: 'root' })
export class SubmissionService {
  private readonly api = inject(ApiClient);

  listAttempts(status?: SubmissionStatus, limit = 50): Observable<SubmissionAttempt[]> {
    let params = new HttpParams().set('limit', limit);
    if (status) {
      params = params.set('status', status);
    }
    return this.api.get<SubmissionAttempt[]>(API_ROUTES.submission.attempts(), { params });
  }

  listEvents(attemptId: string): Observable<SubmissionEvent[]> {
    return this.api.get<SubmissionEvent[]>(API_ROUTES.submission.events({ id: attemptId }));
  }

  resume(attemptId: string, answers: Record<string, string>): Observable<SubmissionAttempt> {
    return this.api.post<SubmissionAttempt>(API_ROUTES.submission.resume({ id: attemptId }), {
      answers,
    });
  }

  abandon(attemptId: string): Observable<SubmissionAttempt> {
    return this.api.post<SubmissionAttempt>(API_ROUTES.submission.abandon({ id: attemptId }), {});
  }
}
