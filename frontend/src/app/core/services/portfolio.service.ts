import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { PortfolioProjectsResponse } from '../../pages/profile/models/portfolio-projects-response.model';
import { PortfolioSyncResult } from '../../pages/profile/models/portfolio-sync-result.model';
import { PortfolioEngagementResponse } from '../../pages/profile/models/portfolio-engagement.model';

@Injectable({ providedIn: 'root' })
export class PortfolioService {
  private http = inject(HttpClient);
  private base = `${environment.apiUrl}/portfolio`;

  listProjects(limit?: number, offset?: number): Observable<PortfolioProjectsResponse> {
    let params = new HttpParams();
    if (limit != null) params = params.set('limit', limit);
    if (offset != null) params = params.set('offset', offset);
    return this.http.get<PortfolioProjectsResponse>(`${this.base}/projects`, { params });
  }

  sync(): Observable<PortfolioSyncResult> {
    return this.http.post<PortfolioSyncResult>(`${this.base}/sync`, {});
  }

  engagement(): Observable<PortfolioEngagementResponse> {
    return this.http.get<PortfolioEngagementResponse>(`${this.base}/engagement`);
  }
}
