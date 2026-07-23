import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { InboxSignal } from '../../pages/applications/models/inbox-signal.model';

@Injectable({ providedIn: 'root' })
export class InboxSignalsService {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiUrl}/inbox/signals`;

  listPending(): Observable<InboxSignal[]> {
    return this.http.get<InboxSignal[]>(this.base, { params: { state: 'pending' } });
  }

  confirm(id: string): Observable<InboxSignal> {
    return this.http.post<InboxSignal>(`${this.base}/${id}/confirm`, {});
  }

  dismiss(id: string): Observable<InboxSignal> {
    return this.http.post<InboxSignal>(`${this.base}/${id}/dismiss`, {});
  }
}
