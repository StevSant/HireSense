import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiClient, API_ROUTES } from '@core/api';
import { NotificationStatus } from '@core/contracts/notification.model';

@Injectable({ providedIn: 'root' })
export class NotificationService {
  private readonly api = inject(ApiClient);

  status(): Observable<NotificationStatus> {
    return this.api.get<NotificationStatus>(API_ROUTES.notifications.status());
  }

  sendTest(): Observable<{ sent: boolean }> {
    return this.api.post<{ sent: boolean }>(API_ROUTES.notifications.test(), {});
  }
}
