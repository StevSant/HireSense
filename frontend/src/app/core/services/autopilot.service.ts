import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { AutopilotDraft } from '../models/autopilot.model';

@Injectable({ providedIn: 'root' })
export class AutopilotService {
  private readonly http = inject(HttpClient);
  private readonly base = '/api/autopilot';

  listDrafts(limit = 20): Observable<AutopilotDraft[]> {
    return this.http.get<AutopilotDraft[]>(`${this.base}/drafts?limit=${limit}`);
  }
}
