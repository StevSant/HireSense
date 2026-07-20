import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { NotificationStatus } from '../models/notification.model';

@Injectable({ providedIn: 'root' })
export class NotificationService {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiUrl}/notifications`;

  status(): Observable<NotificationStatus> {
    return this.http.get<NotificationStatus>(`${this.base}/status`);
  }

  sendTest(): Observable<{ sent: boolean }> {
    return this.http.post<{ sent: boolean }>(`${this.base}/test`, {});
  }
}
