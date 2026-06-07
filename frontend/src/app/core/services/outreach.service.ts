import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { OutreachEvent } from '../../pages/outreach/models/outreach-event.model';
import { OutreachNudge } from '../../pages/outreach/models/outreach-nudge.model';
import { GenerateRequest } from '../../pages/outreach/models/generate-request.model';
import { GenerateResponse } from '../../pages/outreach/models/generate-response.model';
import { RecordRequest } from '../../pages/outreach/models/record-request.model';

@Injectable({ providedIn: 'root' })
export class OutreachService {
  private http = inject(HttpClient);
  private base = `${environment.apiUrl}/outreach`;

  generate(req: GenerateRequest): Observable<GenerateResponse> {
    return this.http.post<GenerateResponse>(`${this.base}/generate`, req);
  }

  record(req: RecordRequest): Observable<OutreachEvent> {
    return this.http.post<OutreachEvent>(`${this.base}/record`, req);
  }

  listEvents(applicationId: string): Observable<OutreachEvent[]> {
    const params = new HttpParams().set('application_id', applicationId);
    return this.http.get<OutreachEvent[]>(`${this.base}/events`, { params });
  }

  dueFollowups(): Observable<OutreachNudge[]> {
    return this.http.post<OutreachNudge[]>(`${this.base}/nudge`, {});
  }
}
