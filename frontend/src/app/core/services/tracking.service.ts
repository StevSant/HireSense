import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiClient, API_ROUTES } from '@core/api';
import { CreateApplicationRequest } from '@core/contracts/create-application-request.model';
import { BatchEvaluationResponse } from '@core/contracts/batch-evaluation-response.model';
import { TrackedApplication } from '@core/contracts/tracked-application.model';
import { UpdateApplicationRequest } from '@core/contracts/update-application-request.model';

@Injectable({ providedIn: 'root' })
export class TrackingService {
  constructor(private api: ApiClient) {}

  list(status?: string): Observable<TrackedApplication[]> {
    const params: Record<string, string> = {};
    if (status) {
      params['status'] = status;
    }
    return this.api.get<TrackedApplication[]>(API_ROUTES.tracking.root(), { params });
  }

  create(body: CreateApplicationRequest): Observable<TrackedApplication> {
    return this.api.post<TrackedApplication>(API_ROUTES.tracking.root(), body);
  }

  update(id: string, body: UpdateApplicationRequest): Observable<TrackedApplication> {
    return this.api.patch<TrackedApplication>(API_ROUTES.tracking.byId({ id }), body);
  }

  delete(id: string): Observable<void> {
    return this.api.delete<void>(API_ROUTES.tracking.byId({ id }));
  }

  batchEvaluate(trackedAppIds: string[]): Observable<BatchEvaluationResponse> {
    return this.api.post<BatchEvaluationResponse>(API_ROUTES.matching.batchEvaluate(), {
      tracked_app_ids: trackedAppIds,
    });
  }
}
