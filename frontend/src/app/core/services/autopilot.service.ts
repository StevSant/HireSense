import { HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiClient, API_ROUTES } from '@core/api';
import { AutopilotDraft } from '@core/contracts/autopilot.model';

@Injectable({ providedIn: 'root' })
export class AutopilotService {
  private readonly api = inject(ApiClient);

  listDrafts(limit = 20): Observable<AutopilotDraft[]> {
    return this.api.get<AutopilotDraft[]>(API_ROUTES.autopilot.drafts(), {
      params: new HttpParams().set('limit', limit),
    });
  }
}
