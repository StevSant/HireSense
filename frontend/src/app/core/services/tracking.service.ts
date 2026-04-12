import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { CreateApplicationRequest } from '../models/create-application-request.model';
import { BatchEvaluationResponse } from '../../pages/tracking/models/batch-evaluation-response.model';
import { TrackedApplication } from '../../pages/tracking/models/tracked-application.model';
import { UpdateApplicationRequest } from '../../pages/tracking/models/update-application-request.model';

@Injectable({ providedIn: 'root' })
export class TrackingService {
  constructor(private http: HttpClient) {}

  list(status?: string): Observable<TrackedApplication[]> {
    const params: Record<string, string> = {};
    if (status) {
      params['status'] = status;
    }
    return this.http.get<TrackedApplication[]>(`${environment.apiUrl}/tracking`, { params });
  }

  create(body: CreateApplicationRequest): Observable<TrackedApplication> {
    return this.http.post<TrackedApplication>(`${environment.apiUrl}/tracking`, body);
  }

  update(id: string, body: UpdateApplicationRequest): Observable<TrackedApplication> {
    return this.http.patch<TrackedApplication>(`${environment.apiUrl}/tracking/${id}`, body);
  }

  delete(id: string): Observable<void> {
    return this.http.delete<void>(`${environment.apiUrl}/tracking/${id}`);
  }

  batchEvaluate(trackedAppIds: string[]): Observable<BatchEvaluationResponse> {
    return this.http.post<BatchEvaluationResponse>(
      `${environment.apiUrl}/matching/batch-evaluate`,
      { tracked_app_ids: trackedAppIds },
    );
  }
}
