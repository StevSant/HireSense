import { Injectable, inject } from '@angular/core';
import { HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { ApiClient, API_ROUTES } from '@core/api';
import { OutreachEvent } from '@core/contracts/outreach-event.model';
import { OutreachNudge } from '@core/contracts/outreach-nudge.model';
import { GenerateRequest } from '@core/contracts/generate-request.model';
import { GenerateResponse } from '@core/contracts/generate-response.model';
import { RecordRequest } from '@core/contracts/record-request.model';

@Injectable({ providedIn: 'root' })
export class OutreachService {
  private api = inject(ApiClient);

  generate(req: GenerateRequest): Observable<GenerateResponse> {
    return this.api.post<GenerateResponse>(API_ROUTES.outreach.generate(), req);
  }

  record(req: RecordRequest): Observable<OutreachEvent> {
    return this.api.post<OutreachEvent>(API_ROUTES.outreach.record(), req);
  }

  listEvents(applicationId: string): Observable<OutreachEvent[]> {
    const params = new HttpParams().set('application_id', applicationId);
    return this.api.get<OutreachEvent[]>(API_ROUTES.outreach.events(), { params });
  }

  dueFollowups(): Observable<OutreachNudge[]> {
    return this.api.post<OutreachNudge[]>(API_ROUTES.outreach.nudge(), {});
  }
}
