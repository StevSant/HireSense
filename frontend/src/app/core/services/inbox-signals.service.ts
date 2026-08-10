import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiClient, API_ROUTES } from '@core/api';
import { InboxSignal } from '@core/contracts/inbox-signal.model';

@Injectable({ providedIn: 'root' })
export class InboxSignalsService {
  private readonly api = inject(ApiClient);

  listPending(): Observable<InboxSignal[]> {
    return this.api.get<InboxSignal[]>(API_ROUTES.inbox.signals(), {
      params: { state: 'pending' },
    });
  }

  confirm(id: string): Observable<InboxSignal> {
    return this.api.post<InboxSignal>(API_ROUTES.inbox.confirmSignal({ id }), {});
  }

  dismiss(id: string): Observable<InboxSignal> {
    return this.api.post<InboxSignal>(API_ROUTES.inbox.dismissSignal({ id }), {});
  }
}
